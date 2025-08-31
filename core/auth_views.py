"""
Authentication views and helper functions.

This module defines the login endpoint used by the front-end as well
as some utility functions for retrieving user and group information
from a request.  By isolating these views from the authentication
class (see ``core.authentication``) we prevent circular imports when
Django REST framework initialises authentication classes.
"""
from __future__ import annotations

from django.contrib.auth import authenticate
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from core.serializers.auth import LoginSerializer
from core.serializers.wechat import WxLoginSerializer, WxCompleteProfileSerializer, WxBindPhoneSerializer
from core.services.audit import log_action
from core.services.wechat import code2session, bind_or_create_user_from_wx
from core.services.wxcrypto import WxCrypto

from .models import User, Group


# ---------------------------------------------------------------------
# Username/password login (no role bypass)
# ---------------------------------------------------------------------
@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """
    Secure login with username/password only (no role bypass).
    Accepts fields:
      - account or username
      - password or pwd
    """
    s = LoginSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    vd = s.validated_data

    username = vd.get('account') or vd.get('username')
    password = vd.get('password') or vd.get('pwd')

    if not username or not password:
        return Response({'ok': False, 'detail': '账号或密码不能为空'}, status=400)

    user = authenticate(request, username=username, password=password)
    if not user:
        # 审计失败尝试（仅记录用户名）
        try:
            log_action(user=None, action='login', object_type='user', object_id=None,
                       detail={'result': 'fail', 'username': username, 'ip': request.META.get('REMOTE_ADDR')})
        except Exception:
            pass
        return Response({'ok': False, 'detail': '用户名或密码错误'}, status=400)

    # 审计成功登录
    try:
        log_action(user=user, action='login', object_type='user', object_id=user.id,
                   detail={'result': 'ok', 'ip': request.META.get('REMOTE_ADDR')})
    except Exception:
        pass

    # 兼容旧 token
    token_obj, _ = Token.objects.get_or_create(user=user)
    # JWT
    refresh = RefreshToken.for_user(user)

    payload: dict[str, object] = {
        'ok': True,
        'token': token_obj.key,
        'jwt_access': str(refresh.access_token),
        'jwt_refresh': str(refresh),
        'role': user.role,
        'user': {
            'id': user.id,
            'username': user.username,
            'name': user.get_full_name() or user.username,
            'role': user.role,
        },
        'expires_in': 7200,  # legacy field for FE compatibility
    }

    if user.group:
        payload['groupBinding'] = {
            'groupId': user.group.id,
            'groupName': user.group.name,
            'inviteCode': user.group.invite_code,
            'bindTime': int((user.group_bind_time or timezone.now()).timestamp()),
        }

    return Response(payload, status=200)

# DRF ScopedRateThrottle uses throttle_scope on the view function
login_view.throttle_scope = 'login'


# ---------------------------------------------------------------------
# WeChat one-tap login / register (then complete profile)
# ---------------------------------------------------------------------
@api_view(['POST'])
@permission_classes([AllowAny])
def wx_login_view(request):
    s = WxLoginSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    js_code = s.validated_data['code']

    # Call WeChat
    try:
        sess = code2session(js_code)
    except Exception as e:
        return Response({'ok': False, 'detail': f'微信登录失败: {e}'}, status=400)

    # Bind or create user
    ip = request.META.get('REMOTE_ADDR')
    user, is_new, need_profile_completion = bind_or_create_user_from_wx(sess, request_ip=ip)

    # Tokens
    token_obj, _ = Token.objects.get_or_create(user=user)
    refresh = RefreshToken.for_user(user)

    payload = {
        'ok': True,
        'isNew': is_new,
        'need_profile_completion': need_profile_completion,
        'token': token_obj.key,  # legacy token
        'jwt_access': str(refresh.access_token),
        'jwt_refresh': str(refresh),
        'role': user.role,
        'user': {
            'id': user.id,
            'username': user.username,
            'name': user.first_name or user.username,
        }
    }

    # 审计
    try:
        log_action(user=user, action='wx_login', object_type='user', object_id=user.id,
                   detail={'isNew': is_new, 'ip': ip})
    except Exception:
        pass

    return Response(payload, status=200)

wx_login_view.throttle_scope = 'wx_login'


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def get_user_for_request(request) -> User | None:
    """Return the authenticated user from the request if available."""
    if not hasattr(request, 'user'):
        return None
    user = request.user
    if user and getattr(user, 'is_authenticated', False):
        return user  # type: ignore
    return None


def get_group_binding_for_user(user: User | None) -> dict | None:
    """Return group binding dict or None."""
    if user and user.group:
        return {
            'groupId': user.group.id,
            'groupName': user.group.name,
            'inviteCode': user.group.invite_code,
            'bindTime': int((user.group_bind_time or timezone.now()).timestamp()),
        }
    return None


# ---------------------------------------------------------------------
# WeChat: complete profile
# ---------------------------------------------------------------------
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def wx_complete_profile_view(request):
    data = WxCompleteProfileSerializer(data=request.data)
    data.is_valid(raise_exception=True)
    user = request.user
    v = data.validated_data
    # Update user basic fields
    user.first_name = v['name']
    user.save(update_fields=['first_name'])
    # Update patient profile
    from core.models import PatientProfile
    prof, _ = PatientProfile.objects.get_or_create(user=user)
    prof.sex = v['sex']
    prof.age = v['age']
    if 'phone' in v:
        prof.phone = v['phone']
    prof.save()

    try:
        log_action(user=user, action='patient_update', object_type='user', object_id=user.id,
                   detail={'op': 'wx_complete_profile'})
    except Exception:
        pass

    return Response({'ok': True})


# ---------------------------------------------------------------------
# WeChat: bind phone
# ---------------------------------------------------------------------
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def wx_bind_phone_view(request):
    data = WxBindPhoneSerializer(data=request.data)
    data.is_valid(raise_exception=True)
    user = request.user
    # ensure user has wechat binding
    if not hasattr(user, 'wechat'):
        return Response({'ok': False, 'detail': '当前用户未绑定微信'}, status=400)
    try:
        decrypted = WxCrypto.decrypt(
            encryptedData=data.validated_data['encryptedData'],
            session_key=user.wechat.session_key,
            iv=data.validated_data['iv'],
        )
        phone = decrypted.get('phoneNumber') or decrypted.get('purePhoneNumber')
        if not phone:
            return Response({'ok': False, 'detail': '无法解出手机号'}, status=400)
        from core.models import PatientProfile
        prof, _ = PatientProfile.objects.get_or_create(user=user)
        prof.phone = phone
        prof.save(update_fields=['phone'])
        try:
            log_action(user=user, action='wx_bind_phone', object_type='user', object_id=user.id,
                       detail={'result': 'ok'})
        except Exception:
            pass
        return Response({'ok': True, 'phone': phone})
    except Exception as e:
        try:
            log_action(user=user, action='wx_bind_phone', object_type='user', object_id=user.id,
                       detail={'result': 'fail', 'err': str(e)})
        except Exception:
            pass
        return Response({'ok': False, 'detail': f'绑定失败: {e}'}, status=400)


# ---------------------------------------------------------------------
# JWT: refresh & logout
# ---------------------------------------------------------------------
@api_view(['POST'])
@permission_classes([AllowAny])
def jwt_refresh_view(request):
    """Return a new access token from refresh token."""
    view = TokenRefreshView.as_view()
    resp = view(request._request)
    from rest_framework.response import Response as DRFResponse
    if isinstance(resp, DRFResponse):
        data = dict(resp.data)
        if 'access' in data and 'jwt_access' not in data:
            data['jwt_access'] = data.pop('access')
        return DRFResponse(data, status=resp.status_code)
    return resp


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def jwt_logout_view(request):
    """Blacklist current user's refresh tokens (all or a given one)."""
    refresh = request.data.get('refresh')
    count = 0
    try:
        if refresh:
            try:
                token = RefreshToken(refresh)
                token.blacklist()
                count = 1
            except Exception:
                pass
        else:
            for token in OutstandingToken.objects.filter(user=request.user):
                try:
                    BlacklistedToken.objects.get_or_create(token=token)
                    count += 1
                except Exception:
                    pass
        return Response({'ok': True, 'blacklisted': count})
    except Exception as e:
        return Response({'ok': False, 'detail': str(e)}, status=400)
