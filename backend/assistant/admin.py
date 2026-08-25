from django.contrib import admin

from assistant.models import AssistantJob, AssistantSetting


@admin.register(AssistantSetting)
class AssistantSettingAdmin(admin.ModelAdmin):
    list_display = ("enabled", "model_name", "ollama_url", "updated_at")


@admin.register(AssistantJob)
class AssistantJobAdmin(admin.ModelAdmin):
    list_display = ("created_at", "job_type", "input_ref", "ok", "outcome", "latency_ms")
    list_filter = ("job_type", "ok", "outcome")
    readonly_fields = ("created_at",)
