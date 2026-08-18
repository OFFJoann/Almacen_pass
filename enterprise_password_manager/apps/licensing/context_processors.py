from .utils import license_status_dict


def license_status(request):
    return {'license_status': license_status_dict()}
