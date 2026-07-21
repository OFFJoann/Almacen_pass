import re
import math
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class ComplexityValidator:
    def validate(self, password, user=None):
        errors = []
        if not re.search(r'[A-Z]', password):
            errors.append(_('La contraseña debe contener al menos una mayúscula'))
        if not re.search(r'[a-z]', password):
            errors.append(_('La contraseña debe contener al menos una minúscula'))
        if not re.search(r'[0-9]', password):
            errors.append(_('La contraseña debe contener al menos un dígito'))
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append(_('La contraseña debe contener al menos un carácter especial'))
        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return _('La contraseña debe contener mayúscula, minúscula, dígito y carácter especial')


class EntropyValidator:
    def validate(self, password, user=None):
        entropy = self.calculate_entropy(password)
        if entropy < 60:
            raise ValidationError(
                _('La entropía de la contraseña es muy baja (%.2f bits). Se requieren mínimo 60 bits.') % entropy
            )

    def calculate_entropy(self, password):
        charset = 0
        if re.search(r'[a-z]', password):
            charset += 26
        if re.search(r'[A-Z]', password):
            charset += 26
        if re.search(r'[0-9]', password):
            charset += 10
        if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            charset += 32
        if charset == 0:
            return 0
        return len(password) * math.log2(charset)

    def get_help_text(self):
        return _('La contraseña debe tener suficiente entropía (mínimo 60 bits)')
