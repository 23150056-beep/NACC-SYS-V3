from rest_framework import serializers

from locations.models import Barangay, Municipality, Province


class ProvinceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Province
        fields = ["psgc_code", "name"]


class MunicipalitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Municipality
        fields = ["psgc_code", "name"]


class BarangaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Barangay
        fields = ["psgc_code", "name"]
