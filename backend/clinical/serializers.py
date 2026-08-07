from rest_framework import serializers
from django.utils import timezone

from clinical.models import (
    InstrumentCatalog, AgencyFormTemplate, ConsentRecord,
    ClinicalInterviewRecord, ProblemEntry, PreAssessment,
    PsychologicalReport, RemarkNote, TreatmentPlan, ResultEntry, CaseReferral,
    OpinionnaireInvite,
)

ALLOWED_REPORT_EXTENSIONS = ("pdf", "doc", "docx")
MAX_REPORT_BYTES = 15 * 1024 * 1024


class InstrumentCatalogSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source="owner.fullname", read_only=True, default=None)

    class Meta:
        model = InstrumentCatalog
        fields = ["id", "title", "publisher", "category", "audience", "age_range", "notes",
                  "owner", "owner_name", "active", "updated_at"]


class AgencyFormTemplateSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source="owner.fullname", read_only=True, default=None)
    fields = serializers.JSONField(required=False, default=list)

    class Meta:
        model = AgencyFormTemplate
        fields = ["id", "form_type", "title", "body", "fields", "version",
                  "owner", "owner_name", "attestation", "attested_at",
                  "active", "updated_at"]
        read_only_fields = ["attested_at", "version"]

    def validate_attestation(self, value):
        if not value:
            raise serializers.ValidationError(
                "You must attest that this form is agency-authored or an official "
                "government form, not a published assessment instrument.")
        return value

    def create(self, validated_data):
        validated_data["attested_at"] = timezone.now()
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Any content edit bumps the version; re-attestation is enforced by the field validator.
        content_changed = (
            ("fields" in validated_data and validated_data["fields"] != instance.fields)
            or ("body" in validated_data and validated_data["body"] != instance.body))
        if content_changed:
            instance.version += 1
            validated_data["attested_at"] = timezone.now()
        return super().update(instance, validated_data)


class ConsentRecordSerializer(serializers.ModelSerializer):
    child_name = serializers.CharField(source="child.fullname", read_only=True)
    template_title = serializers.CharField(source="template.title", read_only=True, default=None)
    recorded_by_name = serializers.CharField(source="recorded_by.fullname", read_only=True, default=None)
    has_scan = serializers.SerializerMethodField()
    scan_filename = serializers.SerializerMethodField()

    class Meta:
        model = ConsentRecord
        fields = ["id", "child", "child_name", "template", "template_title",
                  "signer_name", "signer_relationship", "date", "scan", "has_scan",
                  "scan_filename", "status", "recorded_by", "recorded_by_name",
                  "created_at"]
        read_only_fields = ["recorded_by"]
        extra_kwargs = {"scan": {"write_only": True, "required": False}}

    def get_has_scan(self, obj):
        return bool(obj.scan)

    def get_scan_filename(self, obj):
        return obj.scan.name.rsplit("/", 1)[-1] if obj.scan else ""


class ClinicalInterviewRecordSerializer(serializers.ModelSerializer):
    child_name = serializers.CharField(source="child.fullname", read_only=True)
    template_title = serializers.CharField(source="template.title", read_only=True, default=None)
    interviewer_name = serializers.CharField(source="interviewer.fullname", read_only=True, default=None)
    answers = serializers.JSONField(required=False, default=dict)

    class Meta:
        model = ClinicalInterviewRecord
        fields = ["id", "child", "child_name", "template", "template_title",
                  "answers", "respondent", "interviewer", "interviewer_name",
                  "date", "created_at"]
        read_only_fields = ["interviewer"]


class PreAssessmentSerializer(serializers.ModelSerializer):
    child_name = serializers.CharField(source="child.fullname", read_only=True)
    psychologist_name = serializers.CharField(source="psychologist.fullname", read_only=True, default=None)
    instrument_titles = serializers.SerializerMethodField()
    consent_status = serializers.CharField(source="consent.status", read_only=True, default=None)
    interview_respondent = serializers.CharField(
        source="interview.respondent", read_only=True, default=None)

    class Meta:
        model = PreAssessment
        fields = ["id", "child", "child_name", "psychologist", "psychologist_name",
                  "date", "status", "instruments", "instrument_titles",
                  "consent", "consent_status", "interview", "interview_respondent",
                  "notes", "completed_at", "created_at"]
        read_only_fields = ["psychologist", "status", "completed_at"]

    def get_instrument_titles(self, obj):
        return [i.title for i in obj.instruments.all()]

    def validate(self, attrs):
        # Linked consent/interview must belong to the same child.
        child = attrs.get("child") or (self.instance.child if self.instance else None)
        consent = attrs.get("consent")
        interview = attrs.get("interview")
        if consent and child and consent.child_id != child.id:
            raise serializers.ValidationError({"consent": "That consent belongs to a different child."})
        if interview and child and interview.child_id != child.id:
            raise serializers.ValidationError({"interview": "That interview belongs to a different child."})
        return attrs


class PsychologicalReportSerializer(serializers.ModelSerializer):
    child_name = serializers.CharField(source="child.fullname", read_only=True)
    author_name = serializers.CharField(source="author.fullname", read_only=True, default=None)
    has_text = serializers.SerializerMethodField()

    class Meta:
        model = PsychologicalReport
        fields = ["id", "child", "child_name", "author", "author_name", "file",
                  "original_filename", "report_type", "coverage",
                  "ai_summary", "ai_summary_confirmed", "has_text", "created_at"]
        read_only_fields = ["author", "original_filename", "ai_summary", "ai_summary_confirmed"]
        extra_kwargs = {"file": {"write_only": True}}

    def get_has_text(self, obj):
        return bool(obj.extracted_text)

    def validate_file(self, f):
        ext = (f.name.rsplit(".", 1)[-1] if "." in f.name else "").lower()
        if ext not in ALLOWED_REPORT_EXTENSIONS:
            raise serializers.ValidationError("Upload a PDF or Word document (.pdf, .doc, .docx).")
        if f.size > MAX_REPORT_BYTES:
            raise serializers.ValidationError("File too large (max 15 MB).")
        return f


class CaseReferralSerializer(serializers.ModelSerializer):
    child_name = serializers.CharField(source="child.fullname", read_only=True)
    uploaded_by_name = serializers.CharField(source="uploaded_by.fullname", read_only=True, default=None)
    has_text = serializers.SerializerMethodField()

    class Meta:
        model = CaseReferral
        fields = ["id", "child", "child_name", "uploaded_by", "uploaded_by_name",
                  "file", "original_filename", "description",
                  "ai_summary", "ai_summary_confirmed", "has_text", "created_at"]
        read_only_fields = ["uploaded_by", "original_filename", "ai_summary", "ai_summary_confirmed"]
        extra_kwargs = {"file": {"write_only": True}}

    def get_has_text(self, obj):
        return bool(obj.extracted_text)

    def validate_file(self, f):
        ext = (f.name.rsplit(".", 1)[-1] if "." in f.name else "").lower()
        if ext not in ALLOWED_REPORT_EXTENSIONS:
            raise serializers.ValidationError("Upload a PDF or Word document (.pdf, .doc, .docx).")
        if f.size > MAX_REPORT_BYTES:
            raise serializers.ValidationError("File too large (max 15 MB).")
        return f


class RemarkNoteSerializer(serializers.ModelSerializer):
    child_name = serializers.CharField(source="child.fullname", read_only=True)
    author_name = serializers.CharField(source="author.fullname", read_only=True, default=None)

    class Meta:
        model = RemarkNote
        fields = ["id", "child", "child_name", "author", "author_name",
                  "date", "text", "created_at"]
        read_only_fields = ["author"]


class TreatmentPlanSerializer(serializers.ModelSerializer):
    child_name = serializers.CharField(source="child.fullname", read_only=True)
    author_name = serializers.CharField(source="author.fullname", read_only=True, default=None)

    class Meta:
        model = TreatmentPlan
        fields = ["id", "child", "child_name", "author", "author_name",
                  "objectives", "interventions", "status", "review_date",
                  "created_at", "updated_at"]
        read_only_fields = ["author"]


class ResultEntrySerializer(serializers.ModelSerializer):
    child_name = serializers.CharField(source="child.fullname", read_only=True)
    child_case_type = serializers.CharField(source="child.case_type", read_only=True, default="")
    instrument_title = serializers.CharField(source="instrument.title", read_only=True, default=None)
    entered_by_name = serializers.CharField(source="entered_by.fullname", read_only=True, default=None)

    class Meta:
        model = ResultEntry
        fields = ["id", "child", "child_name", "child_case_type", "pre_assessment",
                  "instrument", "instrument_title", "summary", "classification",
                  "baseline_category", "date", "entered_by", "entered_by_name", "created_at"]
        read_only_fields = ["entered_by"]

    def validate(self, attrs):
        child = attrs.get("child") or (self.instance.child if self.instance else None)
        pa = attrs.get("pre_assessment")
        if pa and child and pa.child_id != child.id:
            raise serializers.ValidationError(
                {"pre_assessment": "That pre-assessment belongs to a different child."})
        return attrs


class OpinionnaireInviteSerializer(serializers.ModelSerializer):
    child_name = serializers.CharField(source="child.fullname", read_only=True)
    template_title = serializers.CharField(source="template.title", read_only=True)
    is_open = serializers.BooleanField(read_only=True)

    class Meta:
        model = OpinionnaireInvite
        fields = ["id", "child", "child_name", "template", "template_title",
                  "token", "status", "answers", "is_open",
                  "expires_at", "submitted_at", "created_at"]
        read_only_fields = ["token", "status", "answers", "expires_at", "submitted_at"]

    def validate_template(self, tpl):
        # Copyright boundary: only agency/government self-report forms may be
        # administered digitally.
        if tpl.form_type != AgencyFormTemplate.SELF_REPORT_GOV:
            raise serializers.ValidationError(
                "Only agency/government self-report forms can be sent to a child. "
                "Published instruments stay on paper.")
        if not tpl.active:
            raise serializers.ValidationError("That form template is inactive.")
        return tpl


class ProblemEntrySerializer(serializers.ModelSerializer):
    child_name = serializers.CharField(source="child.fullname", read_only=True)
    logged_by_name = serializers.CharField(source="logged_by.fullname", read_only=True, default=None)

    class Meta:
        model = ProblemEntry
        fields = ["id", "child", "child_name", "description", "category",
                  "identified_on", "resolved", "logged_by", "logged_by_name", "created_at"]
        read_only_fields = ["logged_by"]
