from roleml.core.actor.manager.bases import BaseManager
from roleml.core.role.base import Role
from roleml.extensions.plugins.partner.base import Partner


class PartnerManager(BaseManager):

    PLUGIN_NAME = 'Partner'

    # noinspection PyMethodMayBeStatic
    def add_role(self, role: Role):
        for attribute_name in role.__class__.plugin_attributes.get(PartnerManager.PLUGIN_NAME, []):
            partner_decl = getattr(role.__class__, attribute_name)
            partner_impl = Partner(partner_decl.relationship_name or attribute_name)
            partner_impl.base = role
            setattr(role, attribute_name, partner_impl)
