from rest_framework import serializers

class ConsultOpenSerializer(serializers.Serializer):
    targetUserId = serializers.IntegerField(min_value=1)
    type = serializers.ChoiceField(choices=['patient','doctor'], required=False)

class ConsultSendSerializer(serializers.Serializer):
    consultId = serializers.IntegerField(min_value=1)
    content = serializers.CharField(max_length=2000, required=False, allow_blank=True)

class ConsultListQuerySerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=['open','replied','closed'], required=False)
    q = serializers.CharField(max_length=64, required=False)
    deptId = serializers.IntegerField(min_value=1, required=False)
    page = serializers.IntegerField(min_value=1, required=False)
    pageSize = serializers.IntegerField(min_value=1, required=False)

class ConsultReadSerializer(serializers.Serializer):
    consultId = serializers.IntegerField(min_value=1)
    upToMessageId = serializers.IntegerField(min_value=1, required=False)

class ConsultHistoryQuerySerializer(serializers.Serializer):
    consultId = serializers.IntegerField(min_value=1)
    page = serializers.IntegerField(min_value=1, required=False)
    pageSize = serializers.IntegerField(min_value=1, required=False)
