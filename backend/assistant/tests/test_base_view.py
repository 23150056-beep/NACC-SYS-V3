from django.test import TestCase
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from assistant.services import AIUnavailable
from assistant.views import AssistantBaseView


class HandleExceptionTest(TestCase):
    """Unit test of AssistantBaseView.handle_exception in isolation — no
    endpoint in this task actually raises AIUnavailable, so the 503
    conversion has to be proven directly. Eight later tasks inherit this
    method, so both directions matter: AIUnavailable must become a 503, and
    everything else must still reach DRF's normal handling untouched."""

    def setUp(self):
        self.view = AssistantBaseView()
        self.view.request = Request(APIRequestFactory().get("/"))
        self.view.args = ()
        self.view.kwargs = {}
        self.view.headers = {}

    def test_ai_unavailable_becomes_a_503_carrying_its_message(self):
        response = self.view.handle_exception(
            AIUnavailable("The assistant is switched off."))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["detail"],
                          "The assistant is switched off.")

    def test_other_exceptions_still_delegate_to_the_default_handler(self):
        response = self.view.handle_exception(PermissionDenied("nope"))
        self.assertEqual(response.status_code, 403)

        response = self.view.handle_exception(NotFound("missing"))
        self.assertEqual(response.status_code, 404)
