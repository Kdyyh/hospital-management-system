import requests
from dataclasses import dataclass
from typing import Optional
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from core.models import WechatAccount, Group, PatientProfile

User = get_user_model()

@dataclass
class WxSession:
    openid: str
    session_key: str
    unionid: Optional[str] = None

def code2session(js_code: str) -> WxSession:
    if not settings.WECHAT_ENABLE:
        raise RuntimeError('WeChat login not enabled on server')
    url = 'https://api.weixin.qq.com/sns/jscode2session'
    params = {
        'appid': settings.WECHAT_APPID,
        'secret': settings.WECHAT_SECRET,
        'js_code': js_code,
        'grant_type': 'authorization_code',
    }
    r = requests.get(url, params=params, timeout=settings.WECHAT_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    if 'errcode' in data and data['errcode'] != 0:
        raise RuntimeError(f"WeChat error {data.get('errcode')}: {data.get('errmsg')}" )
    openid = data.get('openid')
    session_key = data.get('session_key')
    unionid = data.get('unionid')
    if not openid or not session_key:
        raise RuntimeError('Invalid response from WeChat: missing openid/session_key')
    return WxSession(openid=openid, session_key=session_key, unionid=unionid)

def _gen_username(prefix: str = 'wx') -> str:
    ts = int(timezone.now().timestamp())
    return f"{prefix}{ts}"

def bind_or_create_user_from_wx(session: WxSession, *, request_ip: Optional[str]=None):
    try:
        wx = WechatAccount.objects.select_related('user').get(openid=session.openid)
        user = wx.user
        # update session key & last login
        wx.session_key = session.session_key
        wx.unionid = session.unionid or wx.unionid
        wx.last_login_at = timezone.now()
        if request_ip:
            wx.last_login_ip = request_ip
        wx.save(update_fields=['session_key','unionid','last_login_at','last_login_ip'])
        is_new = False
    except WechatAccount.DoesNotExist:
        # create new patient user with minimal info
        user = User.objects.create_user(username=_gen_username(), password=User.objects.make_random_password())
        user.role = 'patient'
        user.save()
        WechatAccount.objects.create(
            user=user, openid=session.openid,
            unionid=session.unionid, session_key=session.session_key,
            last_login_at=timezone.now(), last_login_ip=request_ip
        )
        # also create an empty patient profile to be completed later
        PatientProfile.objects.create(user=user, status='等待入院')
        is_new = True
    # A simple readiness check for profile completion
    need_profile_completion = not bool(getattr(user, 'first_name', '') and getattr(user, 'patient', None) and getattr(user.patient, 'age', None) and getattr(user.patient, 'sex', None))
    return user, is_new, need_profile_completion
