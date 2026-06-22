"""ORM models package — import all models here so Alembic can discover them."""

from uusio.models.customer import Customer, CustomerDataSource  # noqa: F401
from uusio.models.product import Product, ProductWeight  # noqa: F401
from uusio.models.obligation import EPRObligation, EPRRate, ReportingDeadline  # noqa: F401
from uusio.models.submission import PROSubmission  # noqa: F401
from uusio.models.audit import AuditLog, ImportJob  # noqa: F401
from uusio.models.user import User  # noqa: F401
from uusio.models.packaging import PackagingComponent  # noqa: F401
from uusio.models.billing import Invoice  # noqa: F401
from uusio.models.regulation import RegulationEntry  # noqa: F401
from uusio.models.pro_registry import PROOrganisation, CustomerPRORegistration  # noqa: F401
from uusio.models.volumes import ProductMaterialComposition, MonthlySalesVolume  # noqa: F401
