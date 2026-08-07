# Questionnaire Builder + Paper Digitization — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a Psychologist/Admin create questionnaires by hand or by uploading a paper instrument (PDF/image) that is OCR'd + heuristically parsed into an editable draft, then published for use.

**Architecture:** New endpoints in the `assessments` app (Admin+Psychologist-gated via a single revertable role list). A swappable `InstrumentExtractor` interface with a free local `OcrHeuristicExtractor` (PyMuPDF text + Tesseract OCR fallback). A new Admin/Psychologist React page reuses the builder drawer for both manual editing and reviewing extracted drafts.

**Tech Stack:** Django + DRF (SQLite); PyMuPDF + pytesseract + Pillow (free OCR); React + Vite.

**Spec:** [2026-06-27-questionnaire-builder-design.md](../specs/2026-06-27-questionnaire-builder-design.md)

**Conventions:** Backend from `backend/` as `./venv/Scripts/python.exe manage.py <cmd>`. Commits omit any Claude co-author trailer. **Commits are deferred** — the executor holds them until the user asks (matching this repo's flow); the commit steps below are checkpoints.

---

## File Structure

**New (backend):** `assessments/serializers.py`, `assessments/views.py` (replace stub), `assessments/urls.py`, `assessments/extraction/{__init__,base,ocr_heuristic}.py`, `assessments/tests/test_api.py`, migration `0003_*`.
**Modify (backend):** `assessments/models.py`, `accounts/permissions.py`, `config/urls.py`, `requirements.txt`, `README.md`.
**New (frontend):** `src/config/roles.js`, `src/pages/Questionnaires.jsx`.
**Modify (frontend):** `src/App.jsx`, `src/components/Sidebar.jsx`.

---

## Task 1: Model fields + OCR dependencies

**Files:** Modify `backend/requirements.txt`, `backend/assessments/models.py`; Test `backend/assessments/tests/test_models.py`.

- [ ] **Step 1: Add OCR dependencies and install**

Append to `backend/requirements.txt`:
```
PyMuPDF==1.24.10
pytesseract==0.3.13
Pillow==10.4.0
```
Run (from `backend/`): `./venv/Scripts/python.exe -m pip install PyMuPDF==1.24.10 pytesseract==0.3.13 Pillow==10.4.0`
Expected: "Successfully installed PyMuPDF… pytesseract… pillow…". (If a pinned version fails to resolve, install the nearest available and update requirements.txt to match.)

- [ ] **Step 2: Write the failing model test**

Append to `backend/assessments/tests/test_models.py`:
```python
class QuestionnaireFieldsTest(TestCase):
    def test_questionnaire_status_and_question_fields(self):
        from assessments.models import Questionnaire, Question
        qn = Questionnaire.objects.create(title="SDQ", age_group="5-8")
        self.assertEqual(qn.status, "draft")
        q = Question.objects.create(
            questionnaire=qn, question_text="I am kind.",
            question_type="rating_scale", options=[], order=1)
        self.assertEqual(q.order, 1)
        self.assertEqual(q.options, [])
```

- [ ] **Step 3: Run it to verify failure**

Run: `./venv/Scripts/python.exe manage.py test assessments.tests.test_models.QuestionnaireFieldsTest -v 2`
Expected: FAIL (`status`/`options`/`order` don't exist).

- [ ] **Step 4: Add the fields**

In `backend/assessments/models.py`, update `Questionnaire`:
```python
class Questionnaire(models.Model):
    DRAFT, ACTIVE, ARCHIVED = "draft", "active", "archived"
    STATUS_CHOICES = [(DRAFT, "Draft"), (ACTIVE, "Active"), (ARCHIVED, "Archived")]

    title = models.CharField(max_length=150)
    age_group = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tbl_questionnaire"

    def __str__(self):
        return self.title
```
And update `Question` (add `options`, `order`):
```python
class Question(models.Model):
    questionnaire = models.ForeignKey(
        Questionnaire, on_delete=models.CASCADE, related_name="questions")
    question_text = models.TextField()
    question_type = models.CharField(max_length=50)
    options = models.JSONField(default=list, blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tbl_question"
        ordering = ["order", "id"]
```

- [ ] **Step 5: Make migrations and run the test**

Run: `./venv/Scripts/python.exe manage.py makemigrations assessments`
Expected: `0003_…` adding `status`, `options`, `order`.
Run: `./venv/Scripts/python.exe manage.py test assessments.tests.test_models -v 1`
Expected: OK.

- [ ] **Step 6: Commit (deferred — checkpoint only)**

```bash
git add backend/requirements.txt backend/assessments/models.py backend/assessments/migrations/0003_*.py backend/assessments/tests/test_models.py
git commit -m "feat(assessments): questionnaire status + question options/order fields"
```

---

## Task 2: Permission + serializers + CRUD viewset

**Files:** Modify `backend/accounts/permissions.py`, `backend/config/urls.py`; Create `backend/assessments/serializers.py`, `backend/assessments/views.py`, `backend/assessments/urls.py`, `backend/assessments/tests/test_api.py`.

- [ ] **Step 1: Write the failing CRUD + permission test**

Create `backend/assessments/tests/test_api.py`:
```python
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from accounts.models import Role
from assessments.models import Questionnaire

User = get_user_model()


class QuestionnaireApiTest(APITestCase):
    def setUp(self):
        self.admin_role = Role.objects.create(role_name=Role.ADMINISTRATOR)
        self.psy_role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        self.staff_role = Role.objects.create(role_name=Role.STAFF)
        self.admin = User.objects.create_user(
            email="a@racco1.gov.ph", username="a", password="pass1234", role=self.admin_role)
        self.psy = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234", role=self.psy_role)
        self.staff = User.objects.create_user(
            email="s@racco1.gov.ph", username="s", password="pass1234", role=self.staff_role)

    def _auth(self, email):
        token = self.client.post("/api/auth/login/", {
            "email": email, "password": "pass1234"}).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + token)

    def _payload(self):
        return {
            "title": "SDQ", "age_group": "5-8", "status": "draft",
            "questions": [
                {"question_text": "I am kind.", "question_type": "rating_scale", "options": [], "order": 1},
                {"question_text": "Do you sleep well?", "question_type": "yes_no", "options": [], "order": 2},
            ],
        }

    def test_psychologist_can_create_with_questions(self):
        self._auth("p@racco1.gov.ph")
        resp = self.client.post("/api/questionnaires/", self._payload(), format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.data["questions"]), 2)
        self.assertEqual(Questionnaire.objects.count(), 1)

    def test_admin_can_list(self):
        Questionnaire.objects.create(title="X")
        self._auth("a@racco1.gov.ph")
        resp = self.client.get("/api/questionnaires/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)

    def test_staff_forbidden(self):
        self._auth("s@racco1.gov.ph")
        self.assertEqual(self.client.get("/api/questionnaires/").status_code, 403)
        self.assertEqual(
            self.client.post("/api/questionnaires/", self._payload(), format="json").status_code, 403)

    def test_update_replaces_questions(self):
        self._auth("p@racco1.gov.ph")
        qid = self.client.post("/api/questionnaires/", self._payload(), format="json").data["id"]
        upd = self._payload()
        upd["questions"] = [{"question_text": "Only one.", "question_type": "yes_no", "options": [], "order": 1}]
        resp = self.client.put(f"/api/questionnaires/{qid}/", upd, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data["questions"]), 1)

    def test_archive_hides_from_list(self):
        self._auth("a@racco1.gov.ph")
        qid = self.client.post("/api/questionnaires/", self._payload(), format="json").data["id"]
        self.client.post(f"/api/questionnaires/{qid}/archive/")
        self.assertEqual(len(self.client.get("/api/questionnaires/").data), 0)
```

- [ ] **Step 2: Run it to verify failure**

Run: `./venv/Scripts/python.exe manage.py test assessments.tests.test_api -v 2`
Expected: FAIL (404 — no `/api/questionnaires/`).

- [ ] **Step 3: Add the revertable permission**

In `backend/accounts/permissions.py`, append:
```python
# Roles allowed to manage assessment instruments (questionnaires).
# Capstone RBAC matrix = Admin-only; Psychologist added per product decision 2026-06-27.
# TO REVERT to the capstone rule: remove Role.PSYCHOLOGIST from this tuple.
INSTRUMENT_MANAGER_ROLES = (Role.ADMINISTRATOR, Role.PSYCHOLOGIST)


class CanManageInstruments(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and _role_name(request) in INSTRUMENT_MANAGER_ROLES)
```

- [ ] **Step 4: Create the serializers**

Create `backend/assessments/serializers.py`:
```python
from rest_framework import serializers
from assessments.models import Questionnaire, Question


class QuestionSerializer(serializers.ModelSerializer):
    options = serializers.JSONField(required=False, default=list)

    class Meta:
        model = Question
        fields = ["id", "question_text", "question_type", "options", "order"]


class QuestionnaireSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, required=False)

    class Meta:
        model = Questionnaire
        fields = ["id", "title", "age_group", "description", "status", "questions"]

    def _write_questions(self, questionnaire, questions):
        for i, qd in enumerate(questions):
            qd = {**qd}
            qd.setdefault("order", i + 1)
            Question.objects.create(questionnaire=questionnaire, **qd)

    def create(self, validated_data):
        questions = validated_data.pop("questions", [])
        questionnaire = Questionnaire.objects.create(**validated_data)
        self._write_questions(questionnaire, questions)
        return questionnaire

    def update(self, instance, validated_data):
        questions = validated_data.pop("questions", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if questions is not None:
            instance.questions.all().delete()
            self._write_questions(instance, questions)
        return instance
```

- [ ] **Step 5: Create the viewset**

Create `backend/assessments/views.py` (replaces the stub):
```python
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.permissions import CanManageInstruments
from activity.models import ActivityLog
from activity.services import log_activity
from assessments.models import Questionnaire
from assessments.serializers import QuestionnaireSerializer


class QuestionnaireViewSet(viewsets.ModelViewSet):
    permission_classes = [CanManageInstruments]
    pagination_class = None
    serializer_class = QuestionnaireSerializer

    def get_queryset(self):
        qs = Questionnaire.objects.all().order_by("-created_at")
        if self.request.query_params.get("include_archived") != "true":
            qs = qs.exclude(status=Questionnaire.ARCHIVED)
        return qs

    def _log(self, obj, action_name):
        log_activity(self.request.user, action_name, ActivityLog.RECORD,
                     entity_type="Questionnaire", entity_label=obj.title, entity_id=obj.id)

    def perform_create(self, serializer):
        self._log(serializer.save(), ActivityLog.CREATED)

    def perform_update(self, serializer):
        self._log(serializer.save(), ActivityLog.UPDATED)

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        obj = self.get_object()
        obj.status = Questionnaire.ARCHIVED
        obj.save(update_fields=["status", "updated_at"])
        self._log(obj, ActivityLog.ARCHIVED)
        return Response({"status": "archived"}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        obj = self.get_object()
        obj.status = Questionnaire.ACTIVE
        obj.save(update_fields=["status", "updated_at"])
        return Response({"status": "active"}, status=status.HTTP_200_OK)
```

- [ ] **Step 6: Wire URLs**

Create `backend/assessments/urls.py`:
```python
from rest_framework.routers import DefaultRouter
from assessments.views import QuestionnaireViewSet

router = DefaultRouter()
router.register("questionnaires", QuestionnaireViewSet, basename="questionnaire")

urlpatterns = router.urls
```
In `backend/config/urls.py`, add after the activity include:
```python
    path("api/", include("assessments.urls")),
```

- [ ] **Step 7: Run the tests to verify pass**

Run: `./venv/Scripts/python.exe manage.py test assessments.tests.test_api -v 1`
Expected: 5 tests, OK.

- [ ] **Step 8: Commit (deferred — checkpoint only)**

```bash
git add backend/accounts/permissions.py backend/assessments/serializers.py backend/assessments/views.py backend/assessments/urls.py backend/config/urls.py backend/assessments/tests/test_api.py
git commit -m "feat(assessments): questionnaire CRUD API (Admin+Psychologist)"
```

---

## Task 3: Extractor (OCR + heuristics, swappable)

**Files:** Create `backend/assessments/extraction/__init__.py`, `base.py`, `ocr_heuristic.py`; Test in `backend/assessments/tests/test_extraction.py`.

- [ ] **Step 1: Write the failing extractor test**

Create `backend/assessments/tests/test_extraction.py`:
```python
import fitz  # PyMuPDF
from django.test import TestCase
from assessments.extraction.ocr_heuristic import OcrHeuristicExtractor


def _text_pdf(text):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=11)
    return doc.tobytes()


SAMPLE = """Behavioral Checklist
1. The child is kind to others.
2. The child has trouble sleeping?
3. Does the child avoid eye contact?
"""


class OcrHeuristicExtractorTest(TestCase):
    def test_parses_text_pdf_into_questions(self):
        draft = OcrHeuristicExtractor().extract(_text_pdf(SAMPLE), "application/pdf")
        texts = [q["question_text"] for q in draft["questions"]]
        self.assertIn("The child is kind to others.", texts)
        self.assertEqual(len(draft["questions"]), 3)
        self.assertTrue(all(q["order"] == i + 1 for i, q in enumerate(draft["questions"])))
        self.assertEqual(draft["title"], "Behavioral Checklist")
```

- [ ] **Step 2: Run it to verify failure**

Run: `./venv/Scripts/python.exe manage.py test assessments.tests.test_extraction -v 2`
Expected: FAIL (module `assessments.extraction.ocr_heuristic` not found).

- [ ] **Step 3: Create the interface**

Create `backend/assessments/extraction/__init__.py` (empty).
Create `backend/assessments/extraction/base.py`:
```python
class ExtractionError(Exception):
    """Raised when an uploaded instrument cannot be read into a draft."""


class InstrumentExtractor:
    """Turns an uploaded instrument file into a draft questionnaire dict:
    {"title": str, "age_group": str, "questions": [
        {"question_text": str, "question_type": str, "options": list, "order": int}, ...]}
    Swap implementations (OCR/heuristic now; LLM later) without touching callers.
    """

    def extract(self, file_bytes: bytes, content_type: str) -> dict:
        raise NotImplementedError
```

- [ ] **Step 4: Implement the OCR + heuristic extractor**

Create `backend/assessments/extraction/ocr_heuristic.py`:
```python
import io
import re

import fitz  # PyMuPDF

from assessments.extraction.base import ExtractionError, InstrumentExtractor

_QNUM = re.compile(r"^\s*(?:\d{1,3}|[a-zA-Z])[.)]\s+(.*)")
_YESNO = re.compile(r"\byes\b.*\bno\b", re.I)
_SCALE_RUN = re.compile(r"(?:\b[1-5]\b[^\S\n]*){3,}")
_RATING_HINT = re.compile(
    r"\b(never|rarely|sometimes|often|always|strongly\s+disagree|disagree|agree)\b", re.I)


def _ocr_image(image_bytes: bytes) -> str:
    try:
        import pytesseract
        from PIL import Image
    except Exception as exc:  # pragma: no cover - import guard
        raise ExtractionError("OCR engine not available. Install Pillow/pytesseract.") from exc
    try:
        return pytesseract.image_to_string(Image.open(io.BytesIO(image_bytes)))
    except pytesseract.TesseractNotFoundError as exc:
        raise ExtractionError(
            "Tesseract OCR is not installed. Install it for scanned/photo input, "
            "or type the questions manually.") from exc


def _text_from_pdf(file_bytes: bytes) -> str:
    parts = []
    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        for page in doc:
            text = page.get_text("text")
            if text.strip():
                parts.append(text)
            else:  # scanned page -> render + OCR
                parts.append(_ocr_image(page.get_pixmap(dpi=200).tobytes("png")))
    return "\n".join(parts)


def _guess_type(line: str) -> str:
    if _YESNO.search(line):
        return "yes_no"
    if _SCALE_RUN.search(line) or _RATING_HINT.search(line):
        return "rating_scale"
    return "rating_scale"


def _parse(text: str) -> dict:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    title = None
    questions = []
    for line in lines:
        match = _QNUM.match(line)
        if match:
            body = match.group(1).strip()
            questions.append({
                "question_text": body,
                "question_type": _guess_type(line),
                "options": [],
                "order": len(questions) + 1,
            })
        elif line.endswith("?") and len(line) > 8:
            questions.append({
                "question_text": line,
                "question_type": _guess_type(line),
                "options": [],
                "order": len(questions) + 1,
            })
        elif title is None and 3 <= len(line) <= 90 and not line[0].isdigit():
            title = line
    return {"title": title or "Untitled Instrument", "age_group": "", "questions": questions}


class OcrHeuristicExtractor(InstrumentExtractor):
    def extract(self, file_bytes: bytes, content_type: str) -> dict:
        if content_type == "application/pdf":
            text = _text_from_pdf(file_bytes)
        elif content_type in ("image/png", "image/jpeg"):
            text = _ocr_image(file_bytes)
        else:
            raise ExtractionError("Unsupported file type. Upload a PDF, PNG, or JPG.")
        if not text.strip():
            raise ExtractionError("Could not read any text from the file.")
        return _parse(text)
```

Note: simplify the `question_type` line — replace the convoluted expression with `_guess_type(line)`:
```python
                "question_type": _guess_type(line),
```

- [ ] **Step 5: Run the extractor test to verify pass**

Run: `./venv/Scripts/python.exe manage.py test assessments.tests.test_extraction -v 1`
Expected: OK.

- [ ] **Step 6: Commit (deferred — checkpoint only)**

```bash
git add backend/assessments/extraction backend/assessments/tests/test_extraction.py
git commit -m "feat(assessments): free OCR+heuristic instrument extractor"
```

---

## Task 4: `/extract/` upload endpoint

**Files:** Modify `backend/assessments/views.py`; Test append to `backend/assessments/tests/test_api.py`.

- [ ] **Step 1: Write the failing endpoint test**

Append to `backend/assessments/tests/test_api.py`:
```python
import fitz  # PyMuPDF
from django.core.files.uploadedfile import SimpleUploadedFile


class ExtractEndpointTest(QuestionnaireApiTest):
    def _pdf_file(self):
        doc = fitz.open()
        doc.new_page().insert_text((72, 72), "1. The child is calm.\n2. Sleeps well?", fontsize=11)
        return SimpleUploadedFile("form.pdf", doc.tobytes(), content_type="application/pdf")

    def test_extract_returns_draft_without_saving(self):
        self._auth("p@racco1.gov.ph")
        resp = self.client.post("/api/questionnaires/extract/", {"file": self._pdf_file()}, format="multipart")
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.data["questions"]), 2)
        self.assertEqual(Questionnaire.objects.count(), 0)

    def test_extract_forbidden_for_staff(self):
        self._auth("s@racco1.gov.ph")
        resp = self.client.post("/api/questionnaires/extract/", {"file": self._pdf_file()}, format="multipart")
        self.assertEqual(resp.status_code, 403)

    def test_extract_rejects_missing_file(self):
        self._auth("a@racco1.gov.ph")
        resp = self.client.post("/api/questionnaires/extract/", {}, format="multipart")
        self.assertEqual(resp.status_code, 400)
```

- [ ] **Step 2: Run it to verify failure**

Run: `./venv/Scripts/python.exe manage.py test assessments.tests.test_api.ExtractEndpointTest -v 2`
Expected: FAIL (404 — no `extract` action).

- [ ] **Step 3: Add the `extract` action**

In `backend/assessments/views.py`, add imports at the top:
```python
from rest_framework.parsers import MultiPartParser, FormParser
from assessments.extraction.base import ExtractionError
from assessments.extraction.ocr_heuristic import OcrHeuristicExtractor

ALLOWED_UPLOAD_TYPES = ("application/pdf", "image/png", "image/jpeg")
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def get_extractor():
    # Swap point: return an LlmExtractor() here once an API key/budget exists.
    return OcrHeuristicExtractor()
```
Add this action inside `QuestionnaireViewSet`:
```python
    @action(detail=False, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def extract(self, request):
        upload = request.FILES.get("file")
        if not upload:
            return Response({"detail": "No file uploaded."}, status=status.HTTP_400_BAD_REQUEST)
        if upload.size > MAX_UPLOAD_BYTES:
            return Response({"detail": "File too large (max 10 MB)."}, status=status.HTTP_400_BAD_REQUEST)
        if upload.content_type not in ALLOWED_UPLOAD_TYPES:
            return Response({"detail": "Unsupported file type. Upload a PDF, PNG, or JPG."},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            draft = get_extractor().extract(upload.read(), upload.content_type)
        except ExtractionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(draft, status=status.HTTP_200_OK)
```

- [ ] **Step 4: Run the endpoint tests to verify pass, then the full suite**

Run: `./venv/Scripts/python.exe manage.py test assessments.tests.test_api -v 1`
Expected: 8 tests, OK.
Run: `./venv/Scripts/python.exe manage.py test`
Expected: all OK (no regressions).

- [ ] **Step 5: Commit (deferred — checkpoint only)**

```bash
git add backend/assessments/views.py backend/assessments/tests/test_api.py
git commit -m "feat(assessments): /extract endpoint turns uploads into draft questionnaires"
```

---

## Task 5: Frontend route, role config, sidebar

**Files:** Create `frontend/src/config/roles.js`; Modify `frontend/src/App.jsx`, `frontend/src/components/Sidebar.jsx`.

- [ ] **Step 1: Create the single revertable role list**

Create `frontend/src/config/roles.js`:
```js
// Roles allowed to manage assessment instruments (questionnaires).
// Capstone RBAC = admin-only; Psychologist added per product decision 2026-06-27.
// TO REVERT instrument management to admin-only: remove 'Psychologist' from this list.
export const INSTRUMENT_MANAGER_ROLES = ['Administrator', 'Psychologist'];
```

- [ ] **Step 2: Add the route**

In `frontend/src/App.jsx`, add imports:
```jsx
import Questionnaires from './pages/Questionnaires';
import { INSTRUMENT_MANAGER_ROLES } from './config/roles';
```
Add this route after the `/assessment` route:
```jsx
          <Route path="/questionnaires" element={<ProtectedRoute roles={INSTRUMENT_MANAGER_ROLES}><Shell><Questionnaires /></Shell></ProtectedRoute>} />
```

- [ ] **Step 3: Add the sidebar item**

In `frontend/src/components/Sidebar.jsx`, add the import at the top:
```jsx
import { INSTRUMENT_MANAGER_ROLES } from '../config/roles';
```
In the `NAV` array, add under the `Clinical` section (right after the `/assessment` item):
```jsx
  { to: '/questionnaires', label: 'Assessment Instruments', icon: 'clipboard-pen', roles: INSTRUMENT_MANAGER_ROLES },
```

- [ ] **Step 4: Verify build (page comes next; create a placeholder first so the import resolves)**

Create a temporary minimal `frontend/src/pages/Questionnaires.jsx`:
```jsx
import React from 'react';
export default function Questionnaires() { return <div>Questionnaires</div>; }
```
Run (from `frontend/`): `npm run build`
Expected: built, no errors. (Task 6 replaces this file with the real page.)

- [ ] **Step 5: Commit (deferred — checkpoint only)**

```bash
git add frontend/src/config/roles.js frontend/src/App.jsx frontend/src/components/Sidebar.jsx frontend/src/pages/Questionnaires.jsx
git commit -m "feat(questionnaires): admin/psychologist route + nav"
```

---

## Task 6: Questionnaires page — list, builder, digitize

**Files:** Replace `frontend/src/pages/Questionnaires.jsx`.

- [ ] **Step 1: Implement the full page**

Replace `frontend/src/pages/Questionnaires.jsx` with:
```jsx
import React, { useEffect, useRef, useState } from 'react';
import api from '../api/client';
import { useActivity } from '../context/ActivityContext';
import { Card, Button, Badge, Input, Select, FormField, Alert, EmptyState, Icon, iconBtn, PAGE } from '../ui';

const TYPES = [
  { v: 'rating_scale', label: 'Rating scale (1–5)' },
  { v: 'yes_no', label: 'Yes / No' },
  { v: 'multiple_choice', label: 'Multiple choice' },
  { v: 'emotion', label: 'Emotion-based' },
];
const HAS_OPTIONS = (t) => t === 'multiple_choice' || t === 'emotion';
const STATUS_TONE = { draft: 'neutral', active: 'success', archived: 'amber' };
const blankQuestion = (order) => ({ question_text: '', question_type: 'rating_scale', options: [], order });
const blankForm = () => ({ title: '', age_group: '', description: '', status: 'draft', questions: [blankQuestion(1)] });

export default function Questionnaires() {
  const { refresh: refreshActivity } = useActivity();
  const [items, setItems] = useState([]);
  const [form, setForm] = useState(null);
  const [banner, setBanner] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const fileRef = useRef(null);

  const load = () => api.get('/questionnaires/').then((r) => setItems(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const openCreate = () => { setError(''); setBanner(''); setForm(blankForm()); };
  const openEdit = (qn) => {
    setError(''); setBanner('');
    api.get(`/questionnaires/${qn.id}/`).then((r) => setForm({
      ...r.data,
      questions: (r.data.questions.length ? r.data.questions : [blankQuestion(1)]).map((q) => ({ ...q, options: q.options || [] })),
    }));
  };

  const onUpload = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setError(''); setBusy(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const { data } = await api.post('/questionnaires/extract/', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      setForm({
        title: data.title || '', age_group: data.age_group || '', description: '', status: 'draft',
        questions: (data.questions.length ? data.questions : [blankQuestion(1)]).map((q) => ({ ...q, options: q.options || [] })),
      });
      setBanner(`Imported ${data.questions.length} question(s) from “${file.name}”. Review and fix each one before publishing.`);
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not read that file.');
    } finally {
      setBusy(false);
    }
  };

  const setQuestion = (i, patch) => setForm((f) => ({ ...f, questions: f.questions.map((q, idx) => (idx === i ? { ...q, ...patch } : q)) }));
  const addQuestion = () => setForm((f) => ({ ...f, questions: [...f.questions, blankQuestion(f.questions.length + 1)] }));
  const removeQuestion = (i) => setForm((f) => ({ ...f, questions: f.questions.filter((_, idx) => idx !== i) }));
  const move = (i, dir) => setForm((f) => {
    const qs = [...f.questions]; const j = i + dir;
    if (j < 0 || j >= qs.length) return f;
    [qs[i], qs[j]] = [qs[j], qs[i]];
    return { ...f, questions: qs.map((q, idx) => ({ ...q, order: idx + 1 })) };
  });

  const save = async (publish) => {
    setError('');
    const payload = {
      title: form.title, age_group: form.age_group, description: form.description,
      status: publish ? 'active' : (form.status === 'archived' ? 'draft' : form.status),
      questions: form.questions
        .filter((q) => q.question_text.trim())
        .map((q, i) => ({ question_text: q.question_text, question_type: q.question_type, options: HAS_OPTIONS(q.question_type) ? q.options : [], order: i + 1 })),
    };
    if (!payload.title.trim()) { setError('Title is required.'); return; }
    if (payload.questions.length === 0) { setError('Add at least one question.'); return; }
    try {
      if (form.id) await api.put(`/questionnaires/${form.id}/`, payload);
      else await api.post('/questionnaires/', payload);
      setForm(null); load(); refreshActivity();
    } catch (err) {
      setError(JSON.stringify(err.response?.data || 'Save failed'));
    }
  };

  const archive = async (qn) => {
    if (!window.confirm(`Archive “${qn.title}”?`)) return;
    await api.post(`/questionnaires/${qn.id}/archive/`);
    load(); refreshActivity();
  };

  return (
    <div style={{ ...PAGE, position: 'relative' }}>
      <input ref={fileRef} type="file" accept="application/pdf,image/png,image/jpeg" onChange={onUpload} style={{ display: 'none' }} />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
        <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>Build a questionnaire by hand, or digitize a paper instrument.</div>
        <div style={{ display: 'flex', gap: 10 }}>
          <Button variant="secondary" onClick={() => fileRef.current?.click()} disabled={busy} iconLeft={<Icon name={busy ? 'loader' : 'file-up'} size={17} />}>{busy ? 'Reading…' : 'Digitize from paper'}</Button>
          <Button variant="primary" onClick={openCreate} iconLeft={<Icon name="plus" size={17} />}>New Questionnaire</Button>
        </div>
      </div>

      {error && !form && <Alert tone="danger" icon={<Icon name="alert-triangle" size={18} />} style={{ marginBottom: 14 }}>{error}</Alert>}

      <Card padding="0">
        {items.length === 0 ? (
          <EmptyState icon={<Icon name="clipboard-pen" size={24} />} title="No questionnaires yet" description="Create one, or upload a paper instrument to digitize it." />
        ) : (
          <div className="racco-scroll" style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', minWidth: 640, borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: 'var(--ink-50)', borderBottom: '1px solid var(--border)' }}>
                  {['Title', 'Age Group', 'Questions', 'Status', 'Actions'].map((h) => (
                    <th key={h} scope="col" style={{ textAlign: 'left', padding: '12px 16px', fontSize: 11, fontWeight: 800, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {items.map((qn) => (
                  <tr key={qn.id} style={{ borderBottom: '1px solid var(--ink-100)' }}>
                    <td style={{ padding: '12px 16px', fontWeight: 700, fontSize: 13.5, color: 'var(--text-strong)' }}>{qn.title}</td>
                    <td style={{ padding: '12px 16px', fontSize: 13, color: 'var(--text-body)' }}>{qn.age_group || '—'}</td>
                    <td style={{ padding: '12px 16px', fontSize: 13, color: 'var(--text-muted)' }}>{qn.questions?.length ?? 0}</td>
                    <td style={{ padding: '12px 16px' }}><Badge tone={STATUS_TONE[qn.status] || 'neutral'} dot>{qn.status}</Badge></td>
                    <td style={{ padding: '12px 16px' }}>
                      <div style={{ display: 'flex', gap: 6 }}>
                        <button title="Edit" aria-label={`Edit ${qn.title}`} onClick={() => openEdit(qn)} style={iconBtn('var(--blue-600)')}><Icon name="pencil" size={15} /></button>
                        <button title="Archive" aria-label={`Archive ${qn.title}`} onClick={() => archive(qn)} style={iconBtn('var(--red-500)')}><Icon name="archive" size={15} /></button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {form && (
        <div onClick={() => setForm(null)} style={{ position: 'fixed', inset: 0, background: 'rgba(14,19,29,0.32)', display: 'flex', justifyContent: 'flex-end', zIndex: 70, animation: 'racco-fade-in var(--dur-base) var(--ease-out)' }}>
          <div onClick={(e) => e.stopPropagation()} style={{ width: 560, maxWidth: '94%', height: '100%', background: 'var(--surface)', boxShadow: 'var(--shadow-xl)', display: 'flex', flexDirection: 'column', animation: 'racco-slide-left var(--dur-slow) var(--ease-out)' }}>
            <div style={{ padding: '18px 20px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'var(--ink-50)' }}>
              <div style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 17, color: 'var(--text-strong)' }}>{form.id ? 'Edit Questionnaire' : 'New Questionnaire'}</div>
              <button type="button" onClick={() => setForm(null)} aria-label="Close" style={iconBtn('var(--text-muted)')}><Icon name="x" size={17} /></button>
            </div>

            <div className="racco-scroll" style={{ flex: 1, overflowY: 'auto', padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
              {banner && <Alert tone="warning" icon={<Icon name="sparkles" size={18} />}>{banner}</Alert>}
              {error && <Alert tone="danger" icon={<Icon name="alert-triangle" size={18} />}>{error}</Alert>}
              <FormField label="Title" required><Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></FormField>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <FormField label="Age Group"><Input value={form.age_group} onChange={(e) => setForm({ ...form, age_group: e.target.value })} placeholder="e.g. 5-8" /></FormField>
                <FormField label="Status"><Select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}><option value="draft">Draft</option><option value="active">Active</option></Select></FormField>
              </div>
              <FormField label="Description"><Input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></FormField>

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 6 }}>
                <div className="racco-eyebrow" style={{ fontSize: 11 }}>Questions ({form.questions.length})</div>
                <Button variant="ghost" onClick={addQuestion} iconLeft={<Icon name="plus" size={15} />}>Add</Button>
              </div>

              {form.questions.map((q, i) => (
                <div key={i} style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: 12, background: 'var(--ink-50)' }}>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-muted)', paddingTop: 9 }}>{i + 1}</span>
                    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}>
                      <Input value={q.question_text} onChange={(e) => setQuestion(i, { question_text: e.target.value })} placeholder="Question text" />
                      <div style={{ display: 'flex', gap: 8 }}>
                        <Select value={q.question_type} onChange={(e) => setQuestion(i, { question_type: e.target.value })}>
                          {TYPES.map((t) => <option key={t.v} value={t.v}>{t.label}</option>)}
                        </Select>
                      </div>
                      {HAS_OPTIONS(q.question_type) && (
                        <Input value={(q.options || []).join(', ')} onChange={(e) => setQuestion(i, { options: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) })} placeholder="Options, comma-separated" />
                      )}
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      <button title="Move up" onClick={() => move(i, -1)} style={iconBtn('var(--text-muted)', 28)}><Icon name="chevron-up" size={14} /></button>
                      <button title="Move down" onClick={() => move(i, 1)} style={iconBtn('var(--text-muted)', 28)}><Icon name="chevron-down" size={14} /></button>
                      <button title="Remove" onClick={() => removeQuestion(i)} style={iconBtn('var(--red-500)', 28)}><Icon name="trash-2" size={14} /></button>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <div style={{ padding: 16, borderTop: '1px solid var(--border)', display: 'flex', gap: 10 }}>
              <Button variant="secondary" fullWidth onClick={() => save(false)} iconLeft={<Icon name="save" size={16} />}>Save draft</Button>
              <Button variant="primary" fullWidth onClick={() => save(true)} iconLeft={<Icon name="check" size={16} />}>Publish</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify the build**

Run (from `frontend/`): `npm run build`
Expected: built, no errors.

- [ ] **Step 3: Commit (deferred — checkpoint only)**

```bash
git add frontend/src/pages/Questionnaires.jsx
git commit -m "feat(questionnaires): builder page with manual + digitize-from-paper flow"
```

---

## Task 7: README note + end-to-end verification

**Files:** Modify `README.md`.

- [ ] **Step 1: Document the optional Tesseract dependency**

In `README.md`, under Backend setup (after the `pip install` line), add:
```markdown
> **Optional (OCR):** digitizing *scanned/photo* instruments needs the free
> [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) binary installed
> and on PATH. Text-based PDFs work without it; the manual builder always works.
```

- [ ] **Step 2: Full backend suite**

Run (from `backend/`): `./venv/Scripts/python.exe manage.py test`
Expected: all OK (model + CRUD + extractor + extract endpoint + prior suites).

- [ ] **Step 3: Frontend build**

Run (from `frontend/`): `npm run build`
Expected: built, no errors.

- [ ] **Step 4: Browser smoke test (preview)**

Start backend (`runserver`) + preview, log in as the seeded admin (or a Psychologist), open **Assessment Instruments**:
- "New Questionnaire" → add a question, Publish → appears as **active** in the list.
- "Digitize from paper" → upload a small text PDF → drawer opens pre-filled with parsed questions and the review banner → Publish → appears in list.
- Confirm a **Staff** login does **not** see the nav item and `GET /api/questionnaires/` returns 403.

- [ ] **Step 5: Commit (deferred — checkpoint only)**

```bash
git add README.md
git commit -m "docs: note optional Tesseract dependency for OCR"
```
```
