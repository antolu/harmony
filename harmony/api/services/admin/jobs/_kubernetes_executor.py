from __future__ import annotations

import asyncio
import typing

if typing.TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from harmony.api.models.job import Job

_HTTP_NOT_FOUND = 404


class KubernetesJobExecutor:
    """Runs jobs as batch/v1 Kubernetes Jobs (multi-replica / prod).

    The `kubernetes` client is imported lazily so dev installs (subprocess
    executor) never need it. argv and env are built server-side by JobManager;
    this executor never interpolates client-supplied strings into the pod spec.
    """

    def __init__(
        self,
        *,
        namespace: str,
        job_image: str,
        data_pvc_name: str,
        models_pvc_name: str,
    ) -> None:
        self._namespace = namespace
        self._job_image = job_image
        self._data_pvc_name = data_pvc_name
        self._models_pvc_name = models_pvc_name

    @staticmethod
    def _load_client() -> typing.Any:
        try:
            import kubernetes.client  # noqa: PLC0415
            import kubernetes.config  # noqa: PLC0415
        except ImportError as e:  # pragma: no cover - exercised only in k8s installs
            msg = (
                "JOB_EXECUTOR=kubernetes requires the 'kubernetes' client. "
                "Install it (pip install kubernetes) in the API image."
            )
            raise RuntimeError(msg) from e
        try:
            kubernetes.config.load_incluster_config()
        except Exception:
            kubernetes.config.load_kube_config()
        return kubernetes

    def _job_name(self, job: Job) -> str:
        return f"harmony-{job.type}-{job.id}"

    async def submit(self, job: Job, command: list[str], env: dict[str, str]) -> str:
        k8s = self._load_client()
        client = k8s.client
        job_name = self._job_name(job)
        env_vars = [client.V1EnvVar(name=k, value=v) for k, v in env.items()]
        container = client.V1Container(
            name="job",
            image=self._job_image,
            command=command,
            env=env_vars,
            volume_mounts=[
                client.V1VolumeMount(name="data", mount_path="/data"),
                client.V1VolumeMount(name="models", mount_path="/models"),
            ],
        )
        volumes = [
            client.V1Volume(
                name="data",
                persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                    claim_name=self._data_pvc_name
                ),
            ),
            client.V1Volume(
                name="models",
                persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                    claim_name=self._models_pvc_name
                ),
            ),
        ]
        pod_spec = client.V1PodSpec(
            restart_policy="Never", containers=[container], volumes=volumes
        )
        template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(
                labels={"app": "harmony-job", "job-id": job.id}
            ),
            spec=pod_spec,
        )
        spec = client.V1JobSpec(template=template, backoff_limit=0)
        body = client.V1Job(metadata=client.V1ObjectMeta(name=job_name), spec=spec)
        batch = client.BatchV1Api()
        await asyncio.to_thread(
            batch.create_namespaced_job, namespace=self._namespace, body=body
        )
        return job_name

    async def wait(self, job_id: str) -> int | None:
        """Poll the K8s job until it succeeds or fails; returns 0 or 1."""
        import asyncio  # noqa: PLC0415

        k8s = self._load_client()
        client = k8s.client
        batch = client.BatchV1Api()
        while True:
            status = await asyncio.to_thread(
                batch.read_namespaced_job_status,
                name=f"harmony-job-{job_id}",
                namespace=self._namespace,
            )
            cond = status.status
            if cond.succeeded:
                return 0
            if cond.failed:
                return 1
            await asyncio.sleep(5)

    def pause(self, job: Job) -> None:
        msg = "Kubernetes jobs cannot be paused"
        raise NotImplementedError(msg)

    def resume(self, job: Job) -> None:
        msg = "Kubernetes jobs cannot be resumed"
        raise NotImplementedError(msg)

    async def cancel(self, job: Job, *, force: bool = False) -> None:
        k8s = self._load_client()
        client = k8s.client
        batch = client.BatchV1Api()
        try:
            await asyncio.to_thread(
                batch.delete_namespaced_job,
                name=self._job_name(job),
                namespace=self._namespace,
                propagation_policy="Background",
            )
        except client.exceptions.ApiException as e:
            if e.status != _HTTP_NOT_FOUND:
                raise

    def get_log_stream(self, job: Job) -> AsyncIterator[str]:
        return self._stream_pod_logs(job)

    async def _stream_pod_logs(self, job: Job) -> AsyncIterator[str]:
        k8s = self._load_client()
        client = k8s.client
        core = client.CoreV1Api()
        pods = await asyncio.to_thread(
            core.list_namespaced_pod,
            namespace=self._namespace,
            label_selector=f"job-id={job.id}",
        )
        if not pods.items:
            return
        pod_name = pods.items[0].metadata.name
        stream = await asyncio.to_thread(
            core.read_namespaced_pod_log,
            name=pod_name,
            namespace=self._namespace,
            follow=True,
            _preload_content=False,
        )

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[str | None] = asyncio.Queue()

        def _drain() -> None:
            for raw in stream.stream():
                line = raw.decode("utf-8", errors="replace").rstrip("\n")
                loop.call_soon_threadsafe(queue.put_nowait, line)
            loop.call_soon_threadsafe(queue.put_nowait, None)

        reader = loop.run_in_executor(None, _drain)
        try:
            while True:
                line = await queue.get()
                if line is None:
                    break
                yield line
        finally:
            await reader
