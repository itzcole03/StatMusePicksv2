import os
import tempfile
from alembic.config import Config
from alembic import command


def test_alembic_upgrade_head_smoke():
    """Run Alembic upgrade head against a temporary SQLite DB to ensure migrations apply."""
    # Use a temp file DB so migrations that expect a file-backed SQLite work
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_path = tmp.name
    tmp.close()

    db_url = f"sqlite:///{tmp_path}"
    # Export DATABASE_URL for Alembic env.py substitution
    os.environ['DATABASE_URL'] = db_url

    # Build alembic config pointing at backend/alembic
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    alembic_cfg = Config(os.path.join(project_root, 'alembic.ini') if os.path.exists(os.path.join(project_root, 'alembic.ini')) else os.path.join(project_root, 'alembic', 'alembic.ini'))
    # Ensure config uses our DATABASE_URL
    alembic_cfg.set_main_option('script_location', os.path.join(project_root, 'alembic'))
    # Run upgrade head
    command.upgrade(alembic_cfg, 'head')

    # Clean up temp DB
    try:
        os.unlink(tmp_path)
    except Exception:
        pass
