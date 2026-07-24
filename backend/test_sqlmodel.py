from sqlmodel import SQLModel, Field, create_engine
class Parent(SQLModel, table=True):
    id: int = Field(primary_key=True)

class Child(SQLModel, table=True):
    id: int = Field(primary_key=True)
    parent_id: int = Field(foreign_key="parent.id", ondelete="CASCADE")

print("Success")
