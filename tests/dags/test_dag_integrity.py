"""
DAG integrity tests.

TDD: these tests define the expected structure of every Airflow DAG BEFORE
the DAG files are implemented. Mark: @pytest.mark.airflow

Running requires apache-airflow in the Python environment:
    pip install apache-airflow
    AIRFLOW_HOME=/tmp/airflow pytest tests/dags/ -v -m airflow
"""
import os
import sys
import pytest

# Ensure DAGs folder is discoverable
DAG_FOLDER = os.path.join(os.path.dirname(__file__), "..", "..", "dags")


@pytest.fixture(scope="module")
def dagbag():
    """Load all DAGs from the dags/ folder."""
    pytest.importorskip("airflow", reason="apache-airflow not installed")
    os.environ.setdefault("AIRFLOW_HOME", "/tmp/airflow_test")
    os.environ.setdefault("AIRFLOW__CORE__UNIT_TEST_MODE", "True")
    os.environ.setdefault("AIRFLOW__DATABASE__SQL_ALCHEMY_CONN", "sqlite:////tmp/airflow_test/airflow.db")

    from airflow.models import DagBag
    bag = DagBag(dag_folder=DAG_FOLDER, include_examples=False)
    return bag


# ---------------------------------------------------------------------------
# Import sanity
# ---------------------------------------------------------------------------

@pytest.mark.airflow
def test_no_dag_import_errors(dagbag):
    """No DAG should have import-time errors – first gate in CI."""
    errors = dagbag.import_errors
    assert errors == {}, f"DAG import errors: {errors}"


@pytest.mark.airflow
def test_all_expected_dags_are_present(dagbag):
    """All three pipeline DAGs must be registered."""
    expected = {"dag_extract_to_s3", "dag_load_to_clickhouse", "dag_dbt_run"}
    loaded = set(dagbag.dags.keys())
    missing = expected - loaded
    assert not missing, f"Missing DAGs: {missing}"


# ---------------------------------------------------------------------------
# dag_extract_to_s3
# ---------------------------------------------------------------------------

@pytest.mark.airflow
def test_extract_dag_has_four_source_tasks(dagbag):
    """One extraction task per OLTP source (web, oms, wms, marketing)."""
    dag = dagbag.dags["dag_extract_to_s3"]
    task_ids = {t.task_id for t in dag.tasks}
    for source in ("web", "oms", "wms", "marketing"):
        assert any(source in tid for tid in task_ids), (
            f"No task found for source '{source}' in dag_extract_to_s3"
        )


@pytest.mark.airflow
def test_extract_dag_schedule_is_hourly(dagbag):
    dag = dagbag.dags["dag_extract_to_s3"]
    # Accept either cron or @hourly preset
    sched = str(dag.schedule_interval)
    assert "hour" in sched.lower() or sched == "0 * * * *", (
        f"Unexpected schedule: {sched}"
    )


@pytest.mark.airflow
def test_extract_dag_has_no_cycles(dagbag):
    """DAG must be acyclic."""
    dag = dagbag.dags["dag_extract_to_s3"]
    assert dag.test_cycle() is None or not dag.test_cycle()


# ---------------------------------------------------------------------------
# dag_load_to_clickhouse
# ---------------------------------------------------------------------------

@pytest.mark.airflow
def test_load_dag_has_four_source_tasks(dagbag):
    dag = dagbag.dags["dag_load_to_clickhouse"]
    task_ids = {t.task_id for t in dag.tasks}
    for source in ("web", "oms", "wms", "marketing"):
        assert any(source in tid for tid in task_ids), (
            f"No task found for source '{source}' in dag_load_to_clickhouse"
        )


@pytest.mark.airflow
def test_load_dag_has_no_cycles(dagbag):
    dag = dagbag.dags["dag_load_to_clickhouse"]
    assert dag.test_cycle() is None or not dag.test_cycle()


@pytest.mark.airflow
def test_load_dag_waits_for_extract_dag(dagbag):
    """Load DAG must declare an ExternalTaskSensor or have a dependency on extract."""
    dag = dagbag.dags["dag_load_to_clickhouse"]
    task_types = {type(t).__name__ for t in dag.tasks}
    # ExternalTaskSensor or a sensor variant must be present
    sensor_present = any("Sensor" in tt or "Trigger" in tt for tt in task_types)
    assert sensor_present, (
        f"dag_load_to_clickhouse has no sensor/trigger dependency on extract dag. Task types: {task_types}"
    )


# ---------------------------------------------------------------------------
# dag_dbt_run
# ---------------------------------------------------------------------------

@pytest.mark.airflow
def test_dbt_dag_has_dbt_run_task(dagbag):
    dag = dagbag.dags["dag_dbt_run"]
    task_ids = {t.task_id for t in dag.tasks}
    assert any("dbt" in tid.lower() for tid in task_ids), (
        f"No dbt task found in dag_dbt_run. Tasks: {task_ids}"
    )


@pytest.mark.airflow
def test_dbt_dag_waits_for_load_dag(dagbag):
    dag = dagbag.dags["dag_dbt_run"]
    task_types = {type(t).__name__ for t in dag.tasks}
    sensor_present = any("Sensor" in tt or "Trigger" in tt for tt in task_types)
    assert sensor_present, (
        f"dag_dbt_run has no sensor/trigger dependency on load dag. Task types: {task_types}"
    )


@pytest.mark.airflow
def test_dbt_dag_has_no_cycles(dagbag):
    dag = dagbag.dags["dag_dbt_run"]
    assert dag.test_cycle() is None or not dag.test_cycle()


# ---------------------------------------------------------------------------
# Ownership / tags (good practice metadata)
# ---------------------------------------------------------------------------

@pytest.mark.airflow
def test_all_dags_have_owner_set(dagbag):
    for dag_id, dag in dagbag.dags.items():
        assert dag.owner not in (None, "", "airflow"), (
            f"DAG '{dag_id}' has default or missing owner"
        )


@pytest.mark.airflow
def test_all_dags_have_tags(dagbag):
    for dag_id, dag in dagbag.dags.items():
        assert dag.tags, f"DAG '{dag_id}' has no tags"
