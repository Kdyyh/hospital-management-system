from rest_framework import serializers

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()

    def validate_username(self, v):
        v = (v or '').strip()
        if not v:
            raise serializers.ValidationError('用户名不能为空')
        return v

    def validate_password(self, v):
        if not v:
            raise serializers.ValidationError('密码不能为空')
        return v
