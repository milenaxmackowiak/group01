# tatou
A web platform for PDF watermarking. This project is intended for pedagogical use and contains security vulnerabilities. Do not deploy it on an open network.

The commands below are written for a bash terminal on Linux. On another system, adapt them as needed.

## Repository layout

| Path | Contents |
|------|----------|
| `server/src/` | Flask application (`server.py`), watermarking methods, CLI (`watermarking_cli.py`), static web pages |
| `server/test/` | Unit tests, API tests, fuzz tests and security regression tests |
| `server/API.md` | Description of every API route |
| `server/clients/` | Public PGP keys of the RMAP clients (other groups) |
| `db/tatou.sql` | Database schema, loaded by MariaDB on first start |
| `docker-compose.yml` | Server, MariaDB and phpMyAdmin containers |
| `.github/workflows/test.yml` | CI: runs the pytest suite on every push and pull request |
| `artifacts/` | Test, fuzzing, mutation and coverage results |

## 1. Set up

Requirements: Git, Python 3.11 or newer (the container uses 3.12), Docker with the Compose plugin, and optionally [HTTPie](https://httpie.io/) (`http`) for manual API calls.

```bash
git clone https://github.com/milenaxmackowiak/group01.git
cd group01/server

# Create and activate a virtual environment
python3 -m venv .venv
. .venv/bin/activate

# Install the server in editable mode, with pytest
python -m pip install -e ".[dev]"

# Extra tools used for fuzzing, coverage and mutation testing
python -m pip install hypothesis pytest-cov mutmut
```

The server refuses to start without a real `SECRET_KEY`, so export one in every shell where you run the server or the tests:

```bash
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
```

## 2. Run locally (without Docker)

The database only runs inside Docker, so a server started this way is mostly useful for the static pages, `/healthz` and the watermarking CLI. Use the Docker deployment for the full application.

```bash
cd server/src
STORAGE_DIR=../storage python server.py      # listens on http://127.0.0.1:5000
```

The watermarking methods can also be used directly from the command line:

```bash
cd server/src
python -m watermarking_cli methods                                   # list available methods
python -m watermarking_cli explore input.pdf --out tree.json         # dump the PDF structure
python -m watermarking_cli embed input.pdf out.pdf --key-prompt --secret "hello"
```

## 3. Test

All test commands are run from `server/`, with the virtual environment active and `SECRET_KEY` exported. Pytest is configured in `server/pyproject.toml` to collect `test/test_*.py`.

### Unit tests

The unit tests check the watermarking methods and helpers in isolation:

- `test_watermarking_all_methods.py`: embeds and reads back a watermark with every registered method, using `test/test_sample.pdf`
- `test_hanna_watermark.py`: tests for a single watermarking method
- `test_fernet.py`, `test_missing_key.py`: encryption and key handling

```bash
python -m pytest test/test_watermarking_all_methods.py test/test_hanna_watermark.py test/test_fernet.py test/test_missing_key.py -v
```

### API tests

The API tests call the Flask routes through `app.test_client()`, so no running server is needed:

- `test_api.py`: health check, user creation, login and input validation, access control between users, path traversal on delete, `SECRET_KEY` handling
- `test_create_user_email_regression.py`: regression tests for email validation on `/api/create-user`
- `test_security_regressions.py`: regression tests for vulnerabilities that have been fixed

```bash
python -m pytest test/test_api.py test/test_create_user_email_regression.py test/test_security_regressions.py -v
```

Some API tests need the database. Without one (no `DB_USER` set), the routes return `503`. The email regression tests accept that, but five tests in `test_api.py` fail (`test_cant_list_someone_elses_versions`, `test_cant_delete_someone_else_document`, `test_unique_login_username`, `test_delete_document_not_escape_storage_root`, `test_create_user_success`). To run the full API suite against a real MariaDB, run it inside the server container (see [Run the tests in Docker](#run-the-tests-in-docker)). `conftest.py` deletes the test users at the start of each session.

To test the API by hand against a deployed server, see `server/API.md` for every route, for example:

```bash
http -v :5000/healthz
http -v POST :5000/api/create-user login=alice email=alice@example.com password=secret
http -v POST :5000/api/login email=alice@example.com password=secret
```

### Full suite

```bash
python -m pytest                       # quiet
python -m pytest -o addopts="" -v -rs  # verbose, with skip reasons (same as CI)
```

### Fuzz tests

The Hypothesis fuzz tests are not collected by default (their file name does not start with `test_`), so run them explicitly:

```bash
SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))") \
  python -m pytest -o addopts="" -v test/fuzz_create_user_email.py --hypothesis-show-statistics
```

### Coverage analysis

Requires `pytest-cov`, installed in [Set up](#1-set-up).

```bash
python -m pytest --cov=src --cov-report=term-missing   # table with uncovered lines
python -m pytest --cov=src --cov-report=html           # browsable report in htmlcov/index.html
```

The report in `artifacts/common/coverage_report.txt` was produced inside the server container, so the database-backed paths are included (see the next section).

### Mutation testing

`mutmut` is configured in `pyproject.toml` to mutate `src/`:

```bash
mutmut run
mutmut results          # list surviving mutants
mutmut show <mutant>    # diff of one mutant
```

Results are stored in `artifacts/hanna/`.

### Run the tests in Docker

With the containers running, mount the server directory into a one-off server container. It has the database credentials in its environment, so all database tests run for real:

```bash
# from the repository root
docker compose run --rm -v "$PWD/server:/work" -w /work server \
  sh -c 'pip install -q -e ".[dev]" hypothesis pytest-cov && python -m pytest --cov=src --cov-report=term-missing'
```

### Continuous integration

`.github/workflows/test.yml` installs the server with Python 3.12 and runs `python -m pytest -o addopts="" -v -rs` on every push, every pull request and on manual dispatch from the Actions tab. CI has no database, so the five database-dependent tests in `test_api.py` listed above fail there. Use the Docker run for a complete result.

## 4. Deploy

From the repository root:

```bash
# 1. Create the environment file and fill in real values
cp sample.env .env
$EDITOR .env

# 2. Provide the server's RMAP key pair (git-ignored, required by the Dockerfile)
#    server/server_pub.asc and server/server_priv.asc, for example:
gpg --quick-gen-key "Group_01" rsa3072 default never
gpg --armor --export Group_01 > server/server_pub.asc
gpg --armor --export-secret-keys Group_01 > server/server_priv.asc
#    Put the passphrase you chose in RMAP_PASSPHRASE in .env

# 3. Build the image and start server, database and phpMyAdmin
docker compose up --build -d

# 4. Follow the logs
docker compose logs -f

# 5. Check that the API is up
http -v :5000/healthz
```

Then open http://127.0.0.1:5000 in a browser to check the website.

The server listens on port 5000. The database is only reachable on the internal `backend` network. phpMyAdmin is bound to `127.0.0.1:8080` on the VM; reach it from your machine through an SSH tunnel:

```bash
ssh -N -L 8080:127.0.0.1:8080 softsec@softsec-group-01.dsv.local.su.se
```

Useful commands:

```bash
docker compose up --build -d server   # redeploy after a code change
docker compose down                   # stop the containers (data is kept)
docker compose down -v                # stop and delete the database and uploaded files
docker compose exec db mariadb -u root -p tatou   # database shell
```

The schema in `db/tatou.sql` is only loaded when the `db-data` volume is created, so run `docker compose down -v` after changing it.
