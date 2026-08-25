from rest_framework import serializers

from assistant.models import AssistantJob, AssistantSetting


class AssistantSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssistantSetting
        fields = ["enabled", "feature_brief", "feature_doc_intelligence",
                  "feature_remark_polish", "feature_census_narrative",
                  "ollama_url", "model_name", "updated_at"]
        read_only_fields = ["updated_at"]


class AssistantJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssistantJob
        fields = ["id", "job_type", "input_ref", "output_text", "model_used",
                  "latency_ms", "ok", "error", "outcome", "created_at"]
