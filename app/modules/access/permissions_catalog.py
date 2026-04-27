from __future__ import annotations

# ruff: noqa: E501

DEFAULT_PERMISSIONS: tuple[dict[str, str], ...] = (
    {"code": "prepaccess.user.read", "app_code": "prepaccess", "resource": "user", "action": "read"},
    {"code": "prepaccess.user.invite", "app_code": "prepaccess", "resource": "user", "action": "invite"},
    {"code": "prepaccess.role.manage", "app_code": "prepaccess", "resource": "role", "action": "manage"},
    {"code": "prepaccess.permission.read", "app_code": "prepaccess", "resource": "permission", "action": "read"},
    {"code": "prepsettings.settings.manage", "app_code": "prepsettings", "resource": "settings", "action": "manage"},
    {"code": "prepstudents.student.read", "app_code": "prepstudents", "resource": "student", "action": "read"},
    {"code": "prepstudents.student.create", "app_code": "prepstudents", "resource": "student", "action": "create"},
    {"code": "preppeople.employee.read", "app_code": "preppeople", "resource": "employee", "action": "read"},
    {"code": "preplearn.course.create", "app_code": "preplearn", "resource": "course", "action": "create"},
    {"code": "preplearn.course.publish", "app_code": "preplearn", "resource": "course", "action": "publish"},
    {"code": "prepquestion.question.manage", "app_code": "prepquestion", "resource": "question", "action": "manage"},
    {"code": "prepassess.assessment.publish", "app_code": "prepassess", "resource": "assessment", "action": "publish"},
    {"code": "prepattend.attendance.manage", "app_code": "prepattend", "resource": "attendance", "action": "manage"},
    {"code": "preppayroll.payroll.manage", "app_code": "preppayroll", "resource": "payroll", "action": "manage"},
    {"code": "preplive.class.schedule", "app_code": "preplive", "resource": "class", "action": "schedule"},
    {"code": "prepprogress.progress.read", "app_code": "prepprogress", "resource": "progress", "action": "read"},
    {"code": "prepnotify.notification.manage", "app_code": "prepnotify", "resource": "notification", "action": "manage"},
    {"code": "prepbilling.subscription.manage", "app_code": "prepbilling", "resource": "subscription", "action": "manage"},
    {"code": "prepadmissions.lead.manage", "app_code": "prepadmissions", "resource": "lead", "action": "manage"},
    {"code": "prepcrm.contact.manage", "app_code": "prepcrm", "resource": "contact", "action": "manage"},
    {"code": "prepcontent.asset.manage", "app_code": "prepcontent", "resource": "asset", "action": "manage"},
    {"code": "prepreports.report.read", "app_code": "prepreports", "resource": "report", "action": "read"},
    {"code": "prepaudit.audit.read", "app_code": "prepaudit", "resource": "audit", "action": "read"},
    {"code": "prepsupport.ticket.manage", "app_code": "prepsupport", "resource": "ticket", "action": "manage"},
    {"code": "prepmobile.config.manage", "app_code": "prepmobile", "resource": "config", "action": "manage"},
)
