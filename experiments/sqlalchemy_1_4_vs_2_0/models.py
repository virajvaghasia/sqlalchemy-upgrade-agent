from sqlalchemy import Column, ForeignKey, Integer, String, DateTime, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship




Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String)
    comments = relationship("Comment", backref="author")

class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    created_at = Column(DateTime)
    issues = relationship("Issue", backref="project")

issue_labels = Table("issue_labels", Base.metadata,
    Column("issue_id", Integer, ForeignKey("issues.id"), primary_key=True),
    Column("label_id", Integer, ForeignKey("labels.id"), primary_key=True),
)

issue_blocks = Table("issue_blocks", Base.metadata,
    Column("blocker_id", Integer, ForeignKey("issues.id"), primary_key=True),
    Column("blocked_id", Integer, ForeignKey("issues.id"), primary_key=True),
)

class Issue(Base):
    __tablename__ = "issues"
    id = Column(Integer, primary_key=True)
    title = Column(String)
    status = Column(String)
    created_at = Column(DateTime)
    project_id = Column(Integer, ForeignKey("projects.id"))
    comments = relationship("Comment", backref="issue")
    labels = relationship("Label", secondary=issue_labels, backref="issues")
    blocks = relationship("Issue", secondary=issue_blocks, primaryjoin=id==issue_blocks.c.blocker_id, secondaryjoin=id==issue_blocks.c.blocked_id, backref="blocked_by")

class Label(Base):
    __tablename__ = "labels"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    
    
class Comment(Base): 
    __tablename__ = "comments"
    id = Column(Integer, primary_key=True)
    issue_id = Column(Integer, ForeignKey("issues.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    body = Column(String)
    created_at = Column(DateTime)

class IssueAssignment(Base):
    __tablename__ = "issue_assignments"
    issue_id = Column(Integer, ForeignKey("issues.id"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    role = Column(String)
    assigned_at = Column(DateTime)
    issue = relationship("Issue", backref="assignments")
    user = relationship("User", backref="assignments")




