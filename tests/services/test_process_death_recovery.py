"""Real spawned-process death around the single authoritative catalog switch."""
import multiprocessing
import os

import pytest

from kg_mnp.services import execution
from kg_mnp.services.facade import ApplicationService
from kg_mnp.services.projects import get_project
from tests.services.test_core_fencing import pending  # noqa: F401 - fixture


def _die_at_publication(configuration, job_id, when):
    service = ApplicationService(configuration)
    job = service.jobs.claim(worker_id="crash-process")
    assert job.job_id == job_id
    write = execution.save_catalog
    def die(root, catalog):
        if when == "after":
            write(root, catalog)
        # Intentionally skips finally handlers and process cleanup. SQLite
        # releases OS ownership; authority must be decided by the real receipt.
        os._exit(73)
    execution.save_catalog = die
    service.execute_job(job, service.jobs.parameters(job_id))


@pytest.mark.parametrize("when", ["before", "after"])
def test_abrupt_process_exit_is_recovered_from_authoritative_receipt(pending, when):  # noqa: F811
    service, _, project_id, job_id = pending
    before = get_project(service.root, project_id)
    context = multiprocessing.get_context("spawn")
    child = context.Process(target=_die_at_publication, args=(service.configuration, job_id, when))
    child.start()
    try:
        child.join(60)
        assert child.exitcode == 73
    finally:
        if child.is_alive():
            child.terminate()
        child.join(5)
        child.close()
    restarted = ApplicationService(service.configuration)
    job = restarted.jobs.get(job_id)
    recovered = restarted.recover_job(job)
    if when == "before":
        assert recovered is None
        assert get_project(service.root, project_id) == before
    else:
        assert recovered.status == "SUCCEEDED"
        assert recovered.result["source"]["source_id"]
        assert get_project(service.root, project_id).authority_revision == before.authority_revision + 1
        assert restarted.recover_job(job).result == recovered.result
        assert restarted.jobs.cancel(job_id).status == "SUCCEEDED"
