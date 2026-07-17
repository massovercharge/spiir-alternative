import contextvars
from sqlmodel import Field, SQLModel, create_engine, Session, select
from sqlalchemy import event, bindparam
from sqlalchemy.orm import with_loader_criteria, Session as SASession
from sqlalchemy.orm import Mapper

hh_ctx = contextvars.ContextVar("hh_id")

class Base(SQLModel):
    pass

class Item(SQLModel, table=True):
    id: int = Field(primary_key=True)
    household_id: str = Field(default="")
    name: str

engine = create_engine("sqlite:///:memory:")
SQLModel.metadata.create_all(engine)

@event.listens_for(SASession, "do_orm_execute")
def _add_tenant_filter(execute_state):
    try:
        hh_id = hh_ctx.get()
    except LookupError:
        return
    
    if execute_state.is_select:
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(
                SQLModel,
                lambda cls: cls.household_id == bindparam("hh_id", callable_=lambda: hh_ctx.get()) if hasattr(cls, "household_id") else True,
                include_aliases=True
            )
        )

@event.listens_for(Mapper, "before_insert")
def _receive_before_insert(mapper, connection, target):
    if hasattr(target, "household_id"):
        try:
            hh_id = hh_ctx.get()
            if not target.household_id:
                target.household_id = hh_id
        except LookupError:
            pass

hh_ctx.set("C")
with Session(engine) as s:
    s.add(Item(id=1, name="Item C"))
    s.commit()

with Session(engine) as s:
    items = s.exec(select(Item)).all()
    print("Items for C:", [(i.name, i.household_id) for i in items])

