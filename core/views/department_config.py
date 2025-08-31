"""
科室配置管理视图
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from ..models import Group
from ..permissions import IsAdminRole, IsCoreOrSuper


@api_view(['GET'])
@permission_classes([IsAdminRole | IsCoreOrSuper])
def get_department_config(request):
    """获取科室配置信息"""
    department_id = request.query_params.get('id')
    
    if not department_id:
        return Response(
            {'detail': '缺少科室ID参数'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        group = Group.objects.get(id=department_id)
    except Group.DoesNotExist:
        return Response(
            {'detail': '科室不存在'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    # 检查权限：普通管理员只能访问自己科室的配置
    user = request.user
    if user.role == 'admin' and user.group_id != department_id:
        return Response(
            {'detail': '无权访问该科室配置'}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    config_data = {
        'id': group.id,
        'name': group.name,
        'avg_consultation_time': group.avg_consultation_time,
        'max_daily_patients': group.max_daily_patients,
        'working_hours': group.working_hours,
        'priority_rules': group.priority_rules,
        'open': group.open,
        'quota': group.quota
    }
    
    return Response(config_data)


@api_view(['PUT'])
@permission_classes([IsCoreOrSuper])
def update_department_config(request):
    """更新科室配置信息"""
    department_id = request.data.get('id')
    config = request.data.get('config', {})
    
    if not department_id:
        return Response(
            {'detail': '缺少科室ID参数'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        group = Group.objects.get(id=department_id)
    except Group.DoesNotExist:
        return Response(
            {'detail': '科室不存在'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    # 检查权限：核心管理员只能修改自己科室的配置
    user = request.user
    if user.role == 'core' and user.group_id != department_id:
        return Response(
            {'detail': '无权修改该科室配置'}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    # 更新配置字段
    update_fields = []
    
    if 'avg_consultation_time' in config:
        group.avg_consultation_time = config['avg_consultation_time']
        update_fields.append('avg_consultation_time')
    
    if 'max_daily_patients' in config:
        group.max_daily_patients = config['max_daily_patients']
        update_fields.append('max_daily_patients')
    
    if 'working_hours' in config:
        group.working_hours = config['working_hours']
        update_fields.append('working_hours')
    
    if 'priority_rules' in config:
        group.priority_rules = config['priority_rules']
        update_fields.append('priority_rules')
    
    if 'open' in config:
        group.open = config['open']
        update_fields.append('open')
    
    if 'quota' in config:
        group.quota = config['quota']
        update_fields.append('quota')
    
    if update_fields:
        group.save(update_fields=update_fields)
    
    return Response({
        'success': True,
        'message': '科室配置更新成功',
        'department': {
            'id': group.id,
            'name': group.name,
            'avg_consultation_time': group.avg_consultation_time,
            'max_daily_patients': group.max_daily_patients,
            'working_hours': group.working_hours,
            'priority_rules': group.priority_rules,
            'open': group.open,
            'quota': group.quota
        }
    })


@api_view(['GET'])
@permission_classes([IsAdminRole | IsCoreOrSuper])
def list_department_configs(request):
    """列出所有科室的基本配置信息"""
    user = request.user
    
    if user.role == 'super':
        # 超级管理员可以查看所有科室
        groups = Group.objects.all()
    elif user.role == 'core':
        # 核心管理员可以查看所有科室
        groups = Group.objects.all()
    else:
        # 普通管理员只能查看自己科室
        groups = Group.objects.filter(id=user.group_id) if user.group_id else Group.objects.none()
    
    configs = []
    for group in groups:
        configs.append({
            'id': group.id,
            'name': group.name,
            'avg_consultation_time': group.avg_consultation_time,
            'max_daily_patients': group.max_daily_patients,
            'open': group.open,
            'quota': group.quota
        })
    
    return Response(configs)
