"""Introduce role permissions [5994f9ad0489].

Revision ID: 5994f9ad0489
Revises: 0.21.1
Create Date: 2022-10-25 23:52:25.935344

"""

import datetime
import uuid

import sqlalchemy as sa
import sqlmodel
from alembic import op
from sqlalchemy import or_, select

# revision identifiers, used by Alembic.
revision = "5994f9ad0489"
down_revision = "0.21.1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade database schema and/or data, creating a new revision."""
    # Create the rolepermissionschema table to track which permissions a given
    #  role grants
    op.create_table(
        "rolepermissionschema",
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("role_id", sqlmodel.sql.sqltypes.GUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roleschema.id"],
        ),
        sa.PrimaryKeyConstraint("name", "role_id"),
    )
    # get metadata from current connection
    meta = sa.MetaData(bind=op.get_bind())

    # pass in tuple with tables we want to reflect, otherwise whole database
    #  will get reflected
    meta.reflect(
        only=(
            "rolepermissionschema",
            "roleschema",
            "userroleassignmentschema",
            "teamroleassignmentschema",
            "userschema",
        )
    )

    # In order to ensure unique names on roles delete potential admin/guest role
    #  that might have been created previous to this alembic version
    userroleassignmentschema = sa.Table(
        "userroleassignmentschema",
        meta,
    )
    teamroleassignmentschema = sa.Table(
        "teamroleassignmentschema",
        meta,
    )
    roleschema = sa.Table(
        "roleschema",
        meta,
    )
    conn = op.get_bind()
    res = conn.execute(
        select(roleschema.c.id).where(
            roleschema.c.name.in_(["admin", "guest"])
        )
    ).fetchall()

    role_ids = [i[0] for i in res]

    conn.execute(
        userroleassignmentschema.delete().where(
            userroleassignmentschema.c.role_id.in_(role_ids)
        )
    )
    conn.execute(
        teamroleassignmentschema.delete().where(
            teamroleassignmentschema.c.role_id.in_(role_ids)
        )
    )
    conn.execute(
        roleschema.delete().where(
            or_(roleschema.c.name == "admin", roleschema.c.name == "guest")
        )
    )

    # Create the three standard permissions also defined in
    #  zenml.enums.PermissionType
    read = "read"
    write = "write"
    me = "me"

    admin_id = str(uuid.uuid4()).replace("-", "")
    guest_id = str(uuid.uuid4()).replace("-", "")

    # Prefill the roles table with the admin and guest role
    op.bulk_insert(
        sa.Table(
            "roleschema",
            meta,
        ),
        [
            {
                "id": admin_id,
                "name": "admin",
                "created": datetime.datetime.utcnow(),
                "updated": datetime.datetime.utcnow(),
            },
            {
                "id": guest_id,
                "name": "guest",
                "created": datetime.datetime.utcnow(),
                "updated": datetime.datetime.utcnow(),
            },
        ],
    )

    # Give the admin read, write and me permissions,
    # give the guest read and me permissions
    op.bulk_insert(
        sa.Table(
            "rolepermissionschema",
            meta,
        ),
        [
            {"role_id": admin_id, "name": read},
            {"role_id": admin_id, "name": write},
            {"role_id": admin_id, "name": me},
            {"role_id": guest_id, "name": read},
            {"role_id": guest_id, "name": me},
        ],
    )

    # In order to not break permissions for existing users, all existing users
    #  will be assigned the admin role
    userschema = sa.Table(
        "userschema",
        meta,
    )

    conn = op.get_bind()
    res = conn.execute(select(userschema.c.id)).fetchall()
    user_ids = [i[0] for i in res]

    for user_id in user_ids:
        op.bulk_insert(
            sa.Table(
                "userroleassignmentschema",
                meta,
            ),
            [
                {
                    "id": str(uuid.uuid4()).replace("-", ""),
                    "role_id": admin_id,
                    "user_id": user_id,
                    "created": datetime.datetime.utcnow(),
                    "updated": datetime.datetime.utcnow(),
                }
            ],
        )


def downgrade() -> None:
    """Downgrade database schema and/or data back to the previous revision."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("rolepermissionschema")
    # ### end Alembic commands ###