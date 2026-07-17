import contextvars
from sqlmodel import Field, SQLModel, create_engine, Session, select
from sqlalchemy import event, bindparam
from sqlalchemy.orm import with_loader_criteria, Session as SASession

hh_ctx = contextvars.ContextVar("hh_id")

class Base(SQLModel):
    pass

class Item(SQLModel, table=True):
    id: int = Field(primary_key=True)
    household_id: str
    name: str

class GlobalItem(SQLModel, table=True):
    id: int = Field(primary_key=True)
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

with Session(engine) as s:
    s.add(Item(id=1, household_id="A", name="Item A"))
    s.add(Item(id=2, household_id="B", name="Item B"))
    s.add(GlobalItem(id=1, name="Global"))
    s.commit()

hh_ctx.set("A")
with Session(engine) as s:
    items = s.exec(select(Item)).all()
    print("Items for A:", [i.name for i in items])

hh_ctx.set("B")
with Session(engine) as s:
    items = s.exec(select(Item)).all()
    print("Items for B:", [i.name for i in items])
