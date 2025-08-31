from rest_framework import serializers

class WxLoginSerializer(serializers.Serializer):
    code = serializers.CharField()
    rawData = serializers.CharField(required=False, allow_blank=True)
    signature = serializers.CharField(required=False, allow_blank=True)
    encryptedData = serializers.CharField(required=False, allow_blank=True)
    iv = serializers.CharField(required=False, allow_blank=True)

    def validate_code(self, v):
        v = (v or '').strip()
        if not v:
            raise serializers.ValidationError('code不能为空')
        if len(v) < 5 or len(v) > 128:
            raise serializers.ValidationError('code长度不合法')
        return v

class WxCompleteProfileSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=64)
    sex = serializers.ChoiceField(choices=['M','F','O'])
    age = serializers.IntegerField(min_value=1, max_value=120)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=32)


class WxBindPhoneSerializer(serializers.Serializer):
    encryptedData = serializers.CharField()
    iv = serializers.CharField()
