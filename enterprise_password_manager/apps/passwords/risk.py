from collections import Counter

from .models import Vault, PasswordEntry
from .encryption import calculate_entropy, password_strength


def compute_user_risk(user):
    """Mirror of the per-user 'Riesgo General' shown in the user's own dashboard."""
    vault, _ = Vault.objects.get_or_create(user=user)
    entries = PasswordEntry.objects.filter(vault=vault, is_deleted=False, is_obsolete=False)
    total_entries = entries.count()

    weak_passwords_count = 0
    plaintext_passwords = []
    for e in entries:
        try:
            pwd = e.get_password()
            if pwd:
                plaintext_passwords.append((e, pwd))
                if password_strength(pwd)['level'] <= 2:
                    weak_passwords_count += 1
        except Exception:
            pass

    password_counter = Counter(pwd for _, pwd in plaintext_passwords)
    has_duplicates = any(count > 1 for count in password_counter.values())
    compromised_count = entries.filter(is_compromised=True).count()

    all_passwords_count = len(plaintext_passwords)
    avg_entropy = 0
    if plaintext_passwords:
        avg_entropy = sum(calculate_entropy(pwd) for _, pwd in plaintext_passwords) / len(plaintext_passwords)

    score = 100
    score -= min(weak_passwords_count * 20, 50)
    score -= 25 if has_duplicates else 0
    score -= 25 if not user.mfa_enabled else 0
    score -= min(compromised_count * 15, 30)
    total_risk_score = max(0, min(100, score))

    max_entropy = 140
    robustness_pct = min(100, round((avg_entropy / max_entropy) * 100)) if total_entries > 0 else 0
    weak_ratio = weak_passwords_count / total_entries if total_entries > 0 else 0
    robustness_pct = max(0, robustness_pct - round(weak_ratio * 40))

    return {
        'user': user,
        'total_entries': total_entries,
        'weak_passwords_count': weak_passwords_count,
        'compromised_count': compromised_count,
        'has_duplicates': has_duplicates,
        'all_passwords_count': all_passwords_count,
        'avg_entropy': round(avg_entropy, 1),
        'total_risk_score': round(total_risk_score, 1),
        'robustness_pct': robustness_pct,
    }


def risk_label(score):
    if score >= 80:
        return 'Bajo', 'success'
    if score >= 60:
        return 'Moderado', 'warning'
    if score >= 40:
        return 'Alto', 'danger'
    return 'Crítico', 'danger'


def robustness_label(pct):
    if pct >= 80:
        return 'Muy Robusta', 'success'
    if pct >= 60:
        return 'Robusta', 'info'
    if pct >= 40:
        return 'Moderada', 'warning'
    if pct >= 20:
        return 'Débil', 'danger'
    return 'Muy Débil', 'danger'