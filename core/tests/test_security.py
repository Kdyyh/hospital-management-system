import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from core.models import User, Group

pytestmark = pytest.mark.django_db

def login(client, username, password):
    r = client.post(reverse('login_view'), {'username': username, 'password': password}, format='json')
    assert r.status_code in (200, 400, 401)
    return r

def test_no_role_bypass_in_login():
    client = APIClient()
    u = User.objects.create_user(username='u1', password='P@ssw0rd1', role='patient')
    # Try to bypass by sending role
    r = client.post(reverse('login_view'), {'username': 'u1', 'password': 'P@ssw0rd1', 'role': 'super'}, format='json')
    assert r.status_code == 200
    # Fetch profile (requires token header on real flow) - here we just assert login succeeded but role not escalated
    u.refresh_from_db()
    assert u.role == 'patient'

def test_wx_login_is_disabled():
    client = APIClient()
    r = client.post(reverse('wx_login_view'), {'code': 'abc'}, format='json')
    assert r.status_code == 501

def test_patient_creation_uses_strong_password_when_missing():
    client = APIClient()
    g = Group.objects.create(name='A')
    admin = User.objects.create_user(username='admin1', password='P@ssw0rd1', role='admin', group=g)
    # login
    r = client.post(reverse('login_view'), {'username': 'admin1', 'password': 'P@ssw0rd1'}, format='json')
    assert r.status_code == 200
    token = r.data['token']
    client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
    # create patient without password
    resp = client.post('/api/patients/register', {'name': '张三', 'sex': 'M', 'age': 20}, format='json')
    assert resp.status_code in (200, 201)
    assert 'initialPassword' in resp.data
    assert resp.data['initialPassword'] and resp.data['initialPassword'] != 'patient123'


def test_login_returns_jwt_and_legacy_token(db):
    from core.models import User
    from django.urls import reverse
    from rest_framework.test import APIClient
    client = APIClient()
    u = User.objects.create_user(username='u_jwt', password='P@ssw0rd1', role='patient')
    r = client.post(reverse('login_view'), {'username': 'u_jwt', 'password': 'P@ssw0rd1'}, format='json')
    assert r.status_code == 200
    assert 'jwt_access' in r.data and r.data['jwt_access']
    assert 'jwt_refresh' in r.data and r.data['jwt_refresh']
    assert 'token' in r.data and r.data['token']


def test_wechat_login_register_flow(monkeypatch, db):
    from django.urls import reverse
    from rest_framework.test import APIClient
    from core.models import WechatAccount, User

    # Mock code2session to avoid real HTTP
    from core.services import wechat as wxsvc
    def fake_code2session(code: str):
        class S: pass
        s = S()
        s.openid = 'openid_test_123'
        s.session_key = 'sk'
        s.unionid = None
        return s
    monkeypatch.setattr(wxsvc, 'code2session', fake_code2session)

    client = APIClient()
    # First call should create a new user
    r = client.post(reverse('wx_login_view'), {'code': 'abc123'}, format='json')
    assert r.status_code == 200
    assert r.data['ok'] is True
    assert r.data['isNew'] is True
    assert r.data['need_profile_completion'] is True
    token = r.data['token']

    # Second call should log into the same user
    r2 = client.post(reverse('wx_login_view'), {'code': 'abc123'}, format='json')
    assert r2.status_code == 200
    assert r2.data['isNew'] is False

    # Complete profile
    client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
    cp = client.post(reverse('wx_complete_profile_view'), {'name':'张三','sex':'M','age':28,'phone':'13800000000'}, format='json')
    assert cp.status_code == 200


def test_wechat_bind_phone_flow(monkeypatch, db):
    from django.urls import reverse
    from rest_framework.test import APIClient
    from core.models import User, WechatAccount

    # Create a user and bind dummy wechat
    u = User.objects.create_user(username='u_wx', password='P@ssw0rd1', role='patient')
    WechatAccount.objects.create(user=u, openid='openid_bind', session_key='c2Vzc2lvbl9rZXk=', unionid=None)
    client = APIClient()
    # Login (legacy token)
    r = client.post(reverse('login_view'), {'username': 'u_wx', 'password': 'P@ssw0rd1'}, format='json')
    token = r.data['token']
    client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
    # Mock decrypt
    from core.services import wxcrypto as wxc
    def fake_decrypt(encryptedData, session_key, iv):
        return {'phoneNumber': '13800000000'}
    monkeypatch.setattr(wxc.WxCrypto, 'decrypt', staticmethod(fake_decrypt))
    # Bind
    resp = client.post(reverse('wx_bind_phone_view'), {'encryptedData': 'x', 'iv': 'y'}, format='json')
    assert resp.status_code == 200
    assert resp.data['ok'] is True


def test_kpi_permissions_and_visibility(db):
    from rest_framework.test import APIClient
    from django.urls import reverse
    from core.models import User, Group, GroupKPI

    g1 = Group.objects.create(name='A')
    g2 = Group.objects.create(name='B')
    # users
    patient = User.objects.create_user(username='p1', password='P@ssw0rd1', role='patient', group=g1)
    admin = User.objects.create_user(username='a1', password='P@ssw0rd1', role='admin', group=g1)
    core = User.objects.create_user(username='c1', password='P@ssw0rd1', role='core', group=g1)
    superu = User.objects.create_user(username='s1', password='P@ssw0rd1', role='super')

    GroupKPI.objects.create(group=g1, queue_len=5, avg_wait_min=12)
    GroupKPI.objects.create(group=g2, queue_len=7, avg_wait_min=20)

    c = APIClient()

    # patient view my
    r = c.post(reverse('login_view'), {'username':'p1','password':'P@ssw0rd1'}, format='json')
    c.credentials(HTTP_AUTHORIZATION=f"Token {r.data['token']}")
    rr = c.get('/api/kpi/my')
    assert rr.status_code == 200 and rr.data['ok'] is True and rr.data['data']['groupId'] == g1.id

    # admin view department
    c = APIClient()
    r = c.post(reverse('login_view'), {'username':'a1','password':'P@ssw0rd1'}, format='json')
    c.credentials(HTTP_AUTHORIZATION=f"Token {r.data['token']}")
    rr = c.get('/api/kpi/department')
    assert rr.status_code == 200 and rr.data['ok'] is True and rr.data['data']['groupId'] == g1.id

    # super view all
    c = APIClient()
    r = c.post(reverse('login_view'), {'username':'s1','password':'P@ssw0rd1'}, format='json')
    c.credentials(HTTP_AUTHORIZATION=f"Token {r.data['token']}")
    rr = c.get('/api/kpi/all')
    assert rr.status_code == 200 and rr.data['ok'] is True and len(rr.data['data']) >= 2


def test_department_doctors_for_patient(db):
    from rest_framework.test import APIClient
    from django.urls import reverse
    from core.models import User, Group, GroupMember

    g = Group.objects.create(id='g1', name='One')
    # create doctors (admin/core) in the same group
    d1 = User.objects.create_user(username='doc1', password='P@ssw0rd1', role='admin', group=g)
    d2 = User.objects.create_user(username='doc2', password='P@ssw0rd1', role='core', group=g)
    GroupMember.objects.create(group=g, user=d1, role='leader')
    GroupMember.objects.create(group=g, user=d2, role='member')
    # a patient bound to g
    p = User.objects.create_user(username='pat', password='P@ssw0rd1', role='patient', group=g)

    c = APIClient()
    r = c.post(reverse('login_view'), {'username':'pat','password':'P@ssw0rd1'}, format='json')
    c.credentials(HTTP_AUTHORIZATION=f"Token {r.data['token']}")
    resp = c.get('/api/department/doctors')
    assert resp.status_code == 200 and resp.data['ok'] is True
    names = [x['name'] for x in resp.data['data']]
    assert len(names) == 2


def test_department_doctors_filters_and_pagination(db):
    from rest_framework.test import APIClient
    from django.urls import reverse
    from django.utils import timezone
    from datetime import timedelta
    from core.models import User, Group, GroupMember, DoctorShift

    g = Group.objects.create(name='Cardio')
    # Create 3 doctors in group
    d1 = User.objects.create_user(username='doc1', password='P@ssw0rd1', role='admin', group=g, first_name='张三')
    d2 = User.objects.create_user(username='doc2', password='P@ssw0rd1', role='core', group=g, first_name='李四')
    d3 = User.objects.create_user(username='doc3', password='P@ssw0rd1', role='core', group=g, first_name='王五')
    for u in (d1,d2,d3):
        GroupMember.objects.create(group=g, user=u, role='member')
    # Put d2 on duty now
    now = timezone.now()
    DoctorShift.objects.create(user=d2, group=g, start_at=now - timedelta(hours=1), end_at=now + timedelta(hours=1))

    p = User.objects.create_user(username='pat', password='P@ssw0rd1', role='patient', group=g)
    c = APIClient()
    r = c.post(reverse('login_view'), {'username':'pat','password':'P@ssw0rd1'}, format='json')
    c.credentials(HTTP_AUTHORIZATION=f"Token {r.data['token']}")

    # onDutyOnly should return only d2
    resp = c.get('/api/department/doctors?onDutyOnly=1')
    assert resp.status_code == 200 and resp.data['ok'] is True
    ids = [x['id'] for x in resp.data['data']]
    assert ids == [d2.id]

    # search q
    resp = c.get('/api/department/doctors?q=张')
    assert any(x['id']==d1.id for x in resp.data['data'])

    # pagination
    resp = c.get('/api/department/doctors?page=1&pageSize=2')
    assert resp.status_code == 200
    assert resp.data['pagination']['pageSize'] == 2
    assert len(resp.data['data']) <= 2
