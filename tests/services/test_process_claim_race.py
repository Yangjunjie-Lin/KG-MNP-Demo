"""Current JobStore fencing is shared by genuinely competing worker processes."""
import multiprocessing

from kg_mnp.services.facade import ApplicationService
from kg_mnp.services.projects import get_project
from tests.services.test_core_fencing import pending  # noqa: F401 - fixture


def claim(configuration, worker, start, output):
    service = ApplicationService(configuration)
    start.wait(20)
    job = service.jobs.claim(worker_id=worker)
    output.put(None if job is None else (job.job_id, job.fencing_token))


def test_two_process_workers_have_one_claim_and_one_core_commit(pending):  # noqa: F811
    service, _principal, project_id, job_id = pending
    context = multiprocessing.get_context("spawn")
    start, output = context.Event(), context.Queue()
    children = [context.Process(target=claim, args=(service.configuration, f"worker-{i}", start, output)) for i in range(2)]
    try:
        for child in children: child.start()
        start.set()
        outcomes = [output.get(timeout=30) for _ in children]
        for child in children:
            child.join(30)
            assert child.exitcode == 0
        assert sum(item is None for item in outcomes) == 1
        winner = next(item for item in outcomes if item is not None)
        assert winner[0] == job_id
        job = service.jobs.get(job_id)
        assert job.fencing_token == winner[1]
        result = service.execute_job(job, service.jobs.parameters(job_id))
        assert result["batch"]["sources"]
        assert service.recover_job(job).status == "SUCCEEDED"
        assert get_project(service.root, project_id).authority_revision == 1
    finally:
        for child in children:
            if child.is_alive(): child.terminate()
            child.join(10)
        output.close()
