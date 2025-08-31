import bleach
from rest_framework import serializers

class PatientCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=64)
    sex = serializers.ChoiceField(choices=['M','F','O'])
    age = serializers.IntegerField(min_value=1, max_value=120)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=32)
    groupId = serializers.IntegerField(required=False, allow_null=True)
    password = serializers.CharField(required=False, allow_blank=True, write_only=True)

class PatientListQuerySerializer(serializers.Serializer):
    deptId = serializers.IntegerField(required=False, allow_null=True)
    page = serializers.IntegerField(required=False, min_value=1)
    pageSize = serializers.IntegerField(required=False, min_value=1, max_value=200)


def validate_name(self, v):
    v = bleach.clean((v or '').strip(), strip=True)
    if len(v) < 2:
        raise serializers.ValidationError('姓名至少2个字符')
    return v

def validate_phone(self, v):
    v = bleach.clean((v or '').strip(), strip=True)
    return v
