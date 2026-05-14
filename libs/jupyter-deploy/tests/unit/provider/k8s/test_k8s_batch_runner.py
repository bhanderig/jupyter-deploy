import unittest
from unittest.mock import Mock, patch

from kubernetes.client.exceptions import ApiException

from jupyter_deploy.api.k8s.batch import CronJobStatus, JobResultInfo
from jupyter_deploy.exceptions import InstructionNotFoundError
from jupyter_deploy.provider.k8s.k8s_batch_runner import K8sBatchRunner
from jupyter_deploy.provider.resolved_argdefs import StrResolvedInstructionArgument


def _build_args(name: str = "jwt-rotator", scope: str = "router", query: str = "app=jwt-rotator") -> dict:
    return {
        "name": StrResolvedInstructionArgument(argument_name="name", value=name),
        "scope": StrResolvedInstructionArgument(argument_name="scope", value=scope),
        "query": StrResolvedInstructionArgument(argument_name="query", value=query),
    }


class TestK8sBatchRunnerGetCronjobStatus(unittest.TestCase):
    @patch("jupyter_deploy.provider.k8s.k8s_batch_runner.k8s_batch.get_last_job_result")
    @patch("jupyter_deploy.provider.k8s.k8s_batch_runner.k8s_batch.get_cronjob_status")
    def test_returns_idle_status(self, mock_get_status: Mock, mock_last_job: Mock) -> None:
        mock_get_status.return_value = CronJobStatus(
            name="jwt-rotator",
            schedule="0 */6 * * *",
            last_schedule_time="2025-05-14T06:00:00",
            active_count=0,
            suspended=False,
        )
        mock_last_job.return_value = None
        display_manager: Mock = Mock()
        runner = K8sBatchRunner(display_manager=display_manager, api_client=Mock())

        result = runner.execute_instruction("get-cronjob-status", _build_args())

        self.assertEqual(result["Status"].value, "Idle")
        self.assertEqual(result["Details"].value, "0 */6 * * *")
        self.assertIn("SubComponent", result)

    @patch("jupyter_deploy.provider.k8s.k8s_batch_runner.k8s_batch.get_last_job_result")
    @patch("jupyter_deploy.provider.k8s.k8s_batch_runner.k8s_batch.get_cronjob_status")
    def test_returns_suspended_status(self, mock_get_status: Mock, mock_last_job: Mock) -> None:
        mock_get_status.return_value = CronJobStatus(
            name="jwt-rotator", schedule="0 */6 * * *", last_schedule_time="", active_count=0, suspended=True
        )
        mock_last_job.return_value = None
        display_manager: Mock = Mock()
        runner = K8sBatchRunner(display_manager=display_manager, api_client=Mock())

        result = runner.execute_instruction("get-cronjob-status", _build_args())

        self.assertEqual(result["Status"].value, "Suspended")

    @patch("jupyter_deploy.provider.k8s.k8s_batch_runner.k8s_batch.get_last_job_result")
    @patch("jupyter_deploy.provider.k8s.k8s_batch_runner.k8s_batch.get_cronjob_status")
    def test_returns_active_status(self, mock_get_status: Mock, mock_last_job: Mock) -> None:
        mock_get_status.return_value = CronJobStatus(
            name="jwt-rotator", schedule="0 */6 * * *", last_schedule_time="", active_count=1, suspended=False
        )
        mock_last_job.return_value = None
        display_manager: Mock = Mock()
        runner = K8sBatchRunner(display_manager=display_manager, api_client=Mock())

        result = runner.execute_instruction("get-cronjob-status", _build_args())

        self.assertEqual(result["Status"].value, "Active")

    @patch("jupyter_deploy.provider.k8s.k8s_batch_runner.k8s_batch.get_last_job_result")
    @patch("jupyter_deploy.provider.k8s.k8s_batch_runner.k8s_batch.get_cronjob_status")
    def test_returns_active_when_manual_job_running(self, mock_get_status: Mock, mock_last_job: Mock) -> None:
        mock_get_status.return_value = CronJobStatus(
            name="jwt-rotator", schedule="0 */6 * * *", last_schedule_time="", active_count=0, suspended=False
        )
        mock_last_job.return_value = JobResultInfo(name="jwt-rotator-manual-123", status="Running", completion_time="")
        display_manager: Mock = Mock()
        runner = K8sBatchRunner(display_manager=display_manager, api_client=Mock())

        result = runner.execute_instruction("get-cronjob-status", _build_args())

        self.assertEqual(result["Status"].value, "Active")
        self.assertEqual(result["StatusCategory"].value, "in-progress")


class TestK8sBatchRunnerGetCronjobStatusApiError(unittest.TestCase):
    @patch("jupyter_deploy.provider.k8s.k8s_batch_runner.k8s_batch.get_cronjob_status")
    def test_api_exception_bubbles_up(self, mock_get_status: Mock) -> None:
        mock_get_status.side_effect = ApiException(status=404, reason="Not Found")
        runner = K8sBatchRunner(display_manager=Mock(), api_client=Mock())

        with self.assertRaises(ApiException):
            runner.execute_instruction("get-cronjob-status", _build_args())


class TestK8sBatchRunnerCreateJobFromCronjob(unittest.TestCase):
    @patch("jupyter_deploy.provider.k8s.k8s_batch_runner.k8s_batch.create_job_from_cronjob")
    def test_returns_job_name(self, mock_create: Mock) -> None:
        mock_create.return_value = "jwt-rotator-manual-20250514"
        display_manager: Mock = Mock()
        runner = K8sBatchRunner(display_manager=display_manager, api_client=Mock())

        result = runner.execute_instruction("create-job-from-cronjob", _build_args())

        self.assertEqual(result["JobName"].value, "jwt-rotator-manual-20250514")


class TestK8sBatchRunnerCreateJobFromCronjobApiError(unittest.TestCase):
    @patch("jupyter_deploy.provider.k8s.k8s_batch_runner.k8s_batch.create_job_from_cronjob")
    def test_api_exception_bubbles_up(self, mock_create: Mock) -> None:
        mock_create.side_effect = ApiException(status=403, reason="Forbidden")
        runner = K8sBatchRunner(display_manager=Mock(), api_client=Mock())

        with self.assertRaises(ApiException):
            runner.execute_instruction("create-job-from-cronjob", _build_args())


class TestK8sBatchRunnerGetJobLogs(unittest.TestCase):
    def _make_runner(self) -> K8sBatchRunner:
        with patch("jupyter_deploy.provider.k8s.k8s_batch_runner.client") as mock_client_mod:
            mock_client_mod.BatchV1Api.return_value = Mock()
            mock_client_mod.CoreV1Api.return_value = Mock()
            return K8sBatchRunner(display_manager=Mock(), api_client=Mock())

    @patch("jupyter_deploy.provider.k8s.k8s_batch_runner.k8s_batch.find_jobs")
    @patch("jupyter_deploy.provider.k8s.k8s_batch_runner.cmd_utils")
    def test_returns_logs(self, mock_cmd_utils: Mock, mock_find_jobs: Mock) -> None:
        runner = self._make_runner()
        mock_core_api: Mock = runner.core_api  # type: ignore[assignment]

        job: Mock = Mock()
        job.metadata.name = "jwt-rotator-123"
        job.status.start_time = None
        mock_find_jobs.return_value = [job]

        pod: Mock = Mock()
        pod.metadata.name = "jwt-rotator-123-abc"
        mock_core_api.list_namespaced_pod.return_value = Mock(items=[pod])
        mock_cmd_utils.run_cmd_and_capture_output.return_value = "key rotated"

        result = runner.execute_instruction("get-job-logs", _build_args())

        self.assertEqual(result["Logs"].value, "key rotated")
        mock_cmd_utils.run_cmd_and_capture_output.assert_called_once_with(
            ["kubectl", "logs", "jwt-rotator-123-abc", "--namespace", "router"]
        )

    @patch("jupyter_deploy.provider.k8s.k8s_batch_runner.k8s_batch.find_jobs")
    @patch("jupyter_deploy.provider.k8s.k8s_batch_runner.cmd_utils")
    def test_passes_extra_args(self, mock_cmd_utils: Mock, mock_find_jobs: Mock) -> None:
        runner = self._make_runner()
        mock_core_api: Mock = runner.core_api  # type: ignore[assignment]

        job: Mock = Mock()
        job.metadata.name = "jwt-rotator-123"
        job.status.start_time = None
        mock_find_jobs.return_value = [job]

        pod: Mock = Mock()
        pod.metadata.name = "jwt-rotator-123-abc"
        mock_core_api.list_namespaced_pod.return_value = Mock(items=[pod])
        mock_cmd_utils.run_cmd_and_capture_output.return_value = "last 20 lines"

        args = _build_args()
        args["extra"] = StrResolvedInstructionArgument(argument_name="extra", value="--tail=20 --since=1h")
        result = runner.execute_instruction("get-job-logs", args)

        self.assertEqual(result["Logs"].value, "last 20 lines")
        mock_cmd_utils.run_cmd_and_capture_output.assert_called_once_with(
            ["kubectl", "logs", "jwt-rotator-123-abc", "--namespace", "router", "--tail=20", "--since=1h"]
        )


class TestK8sBatchRunnerUnknownInstruction(unittest.TestCase):
    def test_raises_instruction_not_found(self) -> None:
        display_manager: Mock = Mock()
        runner = K8sBatchRunner(display_manager=display_manager, api_client=Mock())

        with self.assertRaises(InstructionNotFoundError):
            runner.execute_instruction("unknown-instruction", _build_args())
