"""
Management command to populate the database with test data.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from datetime import timedelta
import random
from core.models import (
    User, Group, GroupMember, PatientProfile, Inquiry, InquiryReply,
    PInquiry, PInquiryReply, Queue, QueueItem, Task, Ad, WechatAccount,
    OperationLog, GroupKPI, DoctorShift, Consultation, ConsMessage
)


class Command(BaseCommand):
    help = 'Populate database with test data'

    def handle(self, *args, **options):
        self.stdout.write('开始创建测试数据...')
        
        # 创建科室/组
        groups = self.create_groups()
        
        # 创建管理员用户
        admin_users = self.create_admin_users(groups)
        
        # 创建患者用户
        patient_users = self.create_patient_users(groups)
        
        # 创建组员关系
        self.create_group_members(groups, admin_users)
        
        # 创建患者档案
        self.create_patient_profiles(patient_users, groups)
        
        # 创建咨询和回复
        self.create_inquiries(patient_users, groups)
        
        # 创建患者在线咨询
        self.create_patient_inquiries(patient_users, groups)
        
        # 创建队列和排队项
        self.create_queues(groups, patient_users)
        
        # 创建任务
        self.create_tasks(groups, admin_users)
        
        # 创建广告
        self.create_ads()
        
        # 创建微信账号绑定
        self.create_wechat_accounts(patient_users + admin_users)
        
        # 创建操作日志
        self.create_operation_logs(patient_users + admin_users)
        
        # 创建科室KPI
        self.create_group_kpis(groups)
        
        # 创建医生排班
        self.create_doctor_shifts(groups, admin_users)
        
        # 创建咨询会话和消息
        self.create_consultations(groups, patient_users, admin_users)
        
        self.stdout.write(self.style.SUCCESS('测试数据创建完成！'))

    def create_groups(self):
        groups_data = [
            {
                'id': 'g1', 'name': '内科', 'description': '内科疾病诊疗', 'open': True, 'quota': 50,
                'avg_consultation_time': 30, 'max_daily_patients': 50,
                'working_hours': [{'start': '08:30', 'end': '12:00'}, {'start': '13:30', 'end': '17:30'}],
                'priority_rules': {'emergency': 1, 'vip': 2, 'normal': 3}
            },
            {
                'id': 'g2', 'name': '外科', 'description': '外科手术和治疗', 'open': True, 'quota': 40,
                'avg_consultation_time': 20, 'max_daily_patients': 40,
                'working_hours': [{'start': '08:30', 'end': '12:00'}, {'start': '13:30', 'end': '17:30'}],
                'priority_rules': {'emergency': 1, 'vip': 2, 'normal': 3}
            },
            {
                'id': 'g3', 'name': '儿科', 'description': '儿童疾病诊疗', 'open': True, 'quota': 30,
                'avg_consultation_time': 15, 'max_daily_patients': 30,
                'working_hours': [{'start': '08:30', 'end': '12:00'}, {'start': '13:30', 'end': '17:30'}],
                'priority_rules': {'emergency': 1, 'vip': 2, 'normal': 3}
            },
            {
                'id': 'g4', 'name': '妇产科', 'description': '妇产科疾病诊疗', 'open': True, 'quota': 35,
                'avg_consultation_time': 25, 'max_daily_patients': 35,
                'working_hours': [{'start': '08:30', 'end': '12:00'}, {'start': '13:30', 'end': '17:30'}],
                'priority_rules': {'emergency': 1, 'vip': 2, 'normal': 3}
            },
            {
                'id': 'g5', 'name': '急诊科', 'description': '急诊救治', 'open': True, 'quota': 60,
                'avg_consultation_time': 10, 'max_daily_patients': 100,
                'working_hours': [{'start': '00:00', 'end': '23:59'}],  # 24小时开放
                'priority_rules': {'emergency': 1, 'vip': 2, 'normal': 3}
            },
        ]
        
        groups = []
        for data in groups_data:
            group, created = Group.objects.get_or_create(
                id=data['id'],
                defaults=data
            )
            groups.append(group)
            self.stdout.write(f'创建科室: {group.name}')
        
        return groups

    def create_admin_users(self, groups):
        admin_users = []
        admin_data = [
            {'username': 'admin1', 'email': 'admin1@hospital.com', 'role': 'admin', 'group': groups[0]},
            {'username': 'admin2', 'email': 'admin2@hospital.com', 'role': 'admin', 'group': groups[1]},
            {'username': 'core1', 'email': 'core1@hospital.com', 'role': 'core', 'group': groups[2]},
            {'username': 'super', 'email': 'super@hospital.com', 'role': 'super', 'group': None},
        ]
        
        for data in admin_data:
            user, created = User.objects.get_or_create(
                username=data['username'],
                defaults={
                    'email': data['email'],
                    'password': make_password('123456'),
                    'role': data['role'],
                    'group': data['group'],
                    'first_name': data['username'].capitalize(),
                    'last_name': '医生'
                }
            )
            admin_users.append(user)
            self.stdout.write(f'创建管理员: {user.username} ({user.role})')
        
        return admin_users

    def create_patient_users(self, groups):
        patient_users = []
        patient_data = [
            {'username': 'patient1', 'email': 'patient1@example.com', 'group': groups[0]},
            {'username': 'patient2', 'email': 'patient2@example.com', 'group': groups[1]},
            {'username': 'patient3', 'email': 'patient3@example.com', 'group': groups[2]},
            {'username': 'patient4', 'email': 'patient4@example.com', 'group': groups[3]},
            {'username': 'patient5', 'email': 'patient5@example.com', 'group': groups[4]},
            {'username': 'patient6', 'email': 'patient6@example.com', 'group': groups[0]},
            {'username': 'patient7', 'email': 'patient7@example.com', 'group': groups[1]},
            {'username': 'patient8', 'email': 'patient8@example.com', 'group': groups[2]},
        ]
        
        for data in patient_data:
            user, created = User.objects.get_or_create(
                username=data['username'],
                defaults={
                    'email': data['email'],
                    'password': make_password('123456'),
                    'role': 'patient',
                    'group': data['group'],
                    'first_name': data['username'].capitalize(),
                    'last_name': '患者'
                }
            )
            patient_users.append(user)
            self.stdout.write(f'创建患者: {user.username}')
        
        return patient_users

    def create_group_members(self, groups, admin_users):
        for i, group in enumerate(groups):
            if i < len(admin_users):
                GroupMember.objects.get_or_create(
                    group=group,
                    user=admin_users[i],
                    defaults={'role': 'leader' if i % 2 == 0 else 'member'}
                )
                self.stdout.write(f'添加组员: {admin_users[i].username} -> {group.name}')

    def create_patient_profiles(self, patient_users, groups):
        diseases = [
            '高血压', '糖尿病', '冠心病', '肺炎', '骨折',
            '胃炎', '哮喘', '关节炎', '中风', '癌症'
        ]
        statuses = ['等待入院', '住院中', '已出院', '康复中']
        
        for i, user in enumerate(patient_users):
            PatientProfile.objects.get_or_create(
                user=user,
                defaults={
                    'sex': '男' if i % 2 == 0 else '女',
                    'age': random.randint(20, 80),
                    'phone': f'138{random.randint(10000000, 99999999)}',
                    'disease': random.choice(diseases),
                    'status': random.choice(statuses),
                    'group': user.group,
                    'case_report': f'患者主诉：{random.choice(["头痛", "发热", "咳嗽", "胸痛", "腹痛"])}。检查结果：{random.choice(["正常", "异常", "需要进一步检查"])}。',
                    'severity': random.choice(['轻度', '中度', '重度']),
                    'estimated_days': random.randint(3, 21)
                }
            )
            self.stdout.write(f'创建患者档案: {user.username}')

    def create_inquiries(self, patient_users, groups):
        inquiry_titles = [
            '关于治疗方案咨询', '药物副作用问题', '预约检查时间',
            '住院费用咨询', '康复指导建议', '术后注意事项'
        ]
        
        for i, user in enumerate(patient_users[:4]):
            inquiry, created = Inquiry.objects.get_or_create(
                id=f'a{i+1}',
                defaults={
                    'user': user,
                    'title': random.choice(inquiry_titles),
                    'content': f'详细咨询内容：{random.choice(["治疗效果", "药物使用", "检查安排", "费用问题", "康复指导"])}。希望得到专业建议。',
                    'group': user.group,
                    'status': random.choice(['open', 'closed', 'resolved'])
                }
            )
            
            # 创建回复
            if created and random.choice([True, False]):
                InquiryReply.objects.create(
                    inquiry=inquiry,
                    by=user.group.users.filter(role__in=['admin', 'core', 'super']).first() if user.group else None,
                    text=random.choice([
                        '感谢您的咨询，我们会尽快安排。',
                        '建议您按时服药并注意休息。',
                        '请按照医嘱进行康复训练。',
                        '我们会安排专家为您会诊。'
                    ])
                )
            
            self.stdout.write(f'创建咨询: {inquiry.title}')

    def create_patient_inquiries(self, patient_users, groups):
        titles = [
            '在线问诊：感冒症状', '健康咨询：饮食建议',
            '病情咨询：慢性病管理', '用药指导：药物相互作用'
        ]
        
        for i, user in enumerate(patient_users[4:8]):
            inquiry, created = PInquiry.objects.get_or_create(
                id=f'q{i+1}',
                defaults={
                    'user': user,
                    'title': random.choice(titles),
                    'content': f'详细病情描述：{random.choice(["发热咳嗽", "头痛乏力", "胸闷气短", "腹痛腹泻"])}。持续时间：{random.randint(1, 7)}天。',
                    'group': user.group
                }
            )
            
            # 创建回复
            if created and random.choice([True, False]):
                PInquiryReply.objects.create(
                    pinquiry=inquiry,
                    by=user.group.users.filter(role__in=['admin', 'core', 'super']).first() if user.group else None,
                    text=random.choice([
                        '建议多休息，多喝水，观察体温变化。',
                        '请提供更多症状细节以便准确诊断。',
                        '建议来院检查以明确诊断。',
                        '可以尝试以下非处方药缓解症状。'
                    ])
                )
            
            self.stdout.write(f'创建患者在线咨询: {inquiry.title}')

    def create_queues(self, groups, patient_users):
        queue_types = ['普通门诊', '专家门诊', '急诊', '检查', '取药']
        
        for i, group in enumerate(groups):
            queue, created = Queue.objects.get_or_create(
                id=f'queue{i+1}',
                defaults={
                    'name': f'{group.name}{queue_types[i % len(queue_types)]}',
                    'department': group.name,
                    'group': group,
                    'current_number': random.randint(1, 20),
                    'waiting_count': random.randint(5, 30),
                    'estimated_time': f'{random.randint(10, 60)}分钟',
                    'status': 'active'
                }
            )
            
            # 创建排队项
            for j in range(3):
                QueueItem.objects.get_or_create(
                    id=f'item{group.id}{j+1}',
                    defaults={
                        'queue': queue,
                        'patient': patient_users[(i * 2 + j) % len(patient_users)],
                        'number': queue.current_number + j + 1,
                        'status': random.choice(['等待中', '就诊中', '已完成']),
                        'priority': random.choice(['normal', 'high', 'urgent'])
                    }
                )
            
            self.stdout.write(f'创建队列: {queue.name}')

    def create_tasks(self, groups, admin_users):
        task_titles = [
            '病历整理', '药品盘点', '设备检查',
            '患者随访', '报告审核', '培训安排'
        ]
        
        for i, group in enumerate(groups):
            for j in range(2):
                Task.objects.get_or_create(
                    title=f'{group.name}{task_titles[(i + j) % len(task_titles)]}',
                    defaults={
                        'description': f'{task_titles[(i + j) % len(task_titles)]}的详细说明和要求。',
                        'status': random.choice(['pending', 'in_progress', 'completed']),
                        'created_by': admin_users[0],
                        'assigned_to': admin_users[i % len(admin_users)],
                        'group': group
                    }
                )
            
            self.stdout.write(f'为科室 {group.name} 创建任务')

    def create_ads(self):
        ad_texts = [
            '欢迎使用智慧医院系统，为您提供便捷的医疗服务！',
            '疫情期间，请佩戴口罩，保持社交距离。',
            '新患者注册即可享受首次咨询优惠。',
            '专家门诊预约火热进行中，请提前预约。'
        ]
        
        for text in ad_texts:
            Ad.objects.get_or_create(text=text)
            self.stdout.write(f'创建广告: {text[:20]}...')

    def create_wechat_accounts(self, users):
        for user in users:
            WechatAccount.objects.get_or_create(
                user=user,
                defaults={
                    'openid': f'wx_openid_{user.id}_{user.username}',
                    'session_key': f'session_key_{user.id}',
                    'last_login_at': timezone.now() - timedelta(days=random.randint(1, 30))
                }
            )
        self.stdout.write(f'为 {len(users)} 个用户创建微信账号绑定')

    def create_operation_logs(self, users):
        actions = ['login', 'wx_login', 'patient_create', 'patient_update']
        
        for user in users:
            for _ in range(random.randint(1, 5)):
                OperationLog.objects.create(
                    user=user,
                    action=random.choice(actions),
                    object_type='user' if random.choice([True, False]) else 'patient',
                    object_id=str(random.randint(1, 100)),
                    status='success',
                    ip=f'192.168.1.{random.randint(1, 255)}'
                )
        self.stdout.write(f'创建操作日志记录')

    def create_group_kpis(self, groups):
        for group in groups:
            GroupKPI.objects.create(
                group=group,
                queue_len=random.randint(5, 50),
                avg_wait_min=random.randint(10, 120)
            )
            self.stdout.write(f'创建科室KPI: {group.name}')

    def create_doctor_shifts(self, groups, admin_users):
        for group in groups:
            for doctor in admin_users[:3]:  # 前3个管理员作为医生
                if doctor.group == group or doctor.role == 'super':
                    start_time = timezone.now() - timedelta(hours=random.randint(1, 72))
                    DoctorShift.objects.create(
                        user=doctor,
                        group=group,
                        start_at=start_time,
                        end_at=start_time + timedelta(hours=8)
                    )
                    self.stdout.write(f'创建医生排班: {doctor.username} -> {group.name}')

    def create_consultations(self, groups, patient_users, admin_users):
        for group in groups:
            group_patients = [p for p in patient_users if p.group == group]
            group_doctors = [d for d in admin_users if d.group == group or d.role == 'super']
            
            if group_patients and group_doctors:
                for i in range(min(3, len(group_patients))):
                    consultation = Consultation.objects.create(
                        group=group,
                        patient=group_patients[i],
                        doctor=group_doctors[0],
                        status=random.choice(['open', 'replied', 'closed'])
                    )
                    
                    # 创建消息
                    for j in range(random.randint(2, 5)):
                        is_patient = j % 2 == 0
                        sender = group_patients[i] if is_patient else group_doctors[0]
                        ConsMessage.objects.create(
                            consult=consultation,
                            sender=sender,
                            content=random.choice([
                                '您好，我有什么症状？',
                                '建议您先做相关检查。',
                                '检查结果出来了，请查看。',
                                '谢谢医生的建议！',
                                '请按时服药并注意休息。'
                            ])
                        )
                    
                    self.stdout.write(f'创建咨询会话: {group_patients[i].username} -> {group_doctors[0].username}')
