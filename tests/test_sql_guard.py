import pytest

from server.utils.sql_guard import SQLGuardError, validate_readonly_query

ALLOWED = {"user", "company", "job_position", "interview_session"}


def test_simple_select_gets_bounded_limit():
    result = validate_readonly_query("SELECT id, username FROM user", ALLOWED, max_rows=200)
    assert result.sql.endswith("LIMIT 200")
    assert result.tables == ("user",)


def test_existing_large_limit_is_capped():
    result = validate_readonly_query("SELECT id FROM user LIMIT 5000", ALLOWED, max_rows=200)
    assert "LIMIT 200" in result.sql.upper()
    assert result.limit == 200


def test_all_joined_tables_are_authorized():
    result = validate_readonly_query(
        "SELECT u.id, c.name FROM user u JOIN company c ON c.id=u.id LIMIT 20",
        ALLOWED,
    )
    assert result.tables == ("user", "company")


def test_join_to_unknown_table_is_rejected():
    with pytest.raises(SQLGuardError):
        validate_readonly_query(
            "SELECT u.id FROM user u JOIN secret_table s ON s.id=u.id",
            ALLOWED,
        )


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM user WHERE id=1",
        "SELECT * FROM user UNION SELECT * FROM company",
        "WITH x AS (SELECT * FROM user) SELECT * FROM x",
        "SELECT * FROM user WHERE id IN (SELECT id FROM company)",
        "SELECT SLEEP(10) FROM user",
        "SELECT * FROM mysql.user",
        "SELECT * FROM user FOR UPDATE",
        "SELECT * FROM user; SELECT * FROM company",
        "SELECT * FROM user -- comment",
    ],
)
def test_unsafe_queries_are_rejected(sql):
    with pytest.raises(SQLGuardError):
        validate_readonly_query(sql, ALLOWED)


def test_wildcard_and_password_hash_are_rejected():
    with pytest.raises(SQLGuardError):
        validate_readonly_query("SELECT * FROM user", ALLOWED)
    with pytest.raises(SQLGuardError):
        validate_readonly_query(
            "SELECT id, password_hash FROM user",
            ALLOWED,
            denied_columns={"password_hash"},
        )


def test_count_star_is_allowed():
    result = validate_readonly_query("SELECT COUNT(*) AS total FROM user", ALLOWED)
    assert result.tables == ("user",)
