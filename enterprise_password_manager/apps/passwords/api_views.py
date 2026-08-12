from rest_framework import viewsets, permissions, status, decorators
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import PasswordEntry, Folder, Category, Tag, Vault
from .serializers import (
    PasswordEntrySerializer, PasswordEntryListSerializer,
    FolderSerializer, CategorySerializer, TagSerializer,
    ShareSerializer, VaultSerializer
)
from .encryption import generate_password, generate_passphrase, calculate_entropy


class PasswordEntryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        vault, _ = Vault.objects.get_or_create(user=self.request.user)
        qs = PasswordEntry.objects.filter(vault=vault, is_deleted=False, is_obsolete=False)
        folder = self.request.query_params.get('folder')
        category = self.request.query_params.get('category')
        search = self.request.query_params.get('search')
        if folder:
            qs = qs.filter(folder_id=folder)
        if category:
            qs = qs.filter(category_id=category)
        if search:
            qs = qs.filter(name__icontains=search)
        return qs

    def get_serializer_class(self):
        if self.action == 'list':
            return PasswordEntryListSerializer
        return PasswordEntrySerializer

    def perform_create(self, serializer):
        vault, _ = Vault.objects.get_or_create(user=self.request.user)
        serializer.save(vault=vault)


class FolderViewSet(viewsets.ModelViewSet):
    serializer_class = FolderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Folder.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Category.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class TagViewSet(viewsets.ModelViewSet):
    serializer_class = TagSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Tag.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_generate_password(request):
    length = int(request.query_params.get('length', 24))
    use_upper = request.query_params.get('upper', 'true').lower() == 'true'
    use_lower = request.query_params.get('lower', 'true').lower() == 'true'
    use_digits = request.query_params.get('digits', 'true').lower() == 'true'
    use_symbols = request.query_params.get('symbols', 'true').lower() == 'true'
    exclude_similar = request.query_params.get('exclude_similar', 'false').lower() == 'true'
    exclude_ambiguous = request.query_params.get('exclude_ambiguous', 'false').lower() == 'true'
    passphrase = request.query_params.get('passphrase', 'false').lower() == 'true'
    num_words = int(request.query_params.get('num_words', 4))

    if passphrase:
        password = generate_passphrase(num_words)
    else:
        password = generate_password(length, use_upper, use_lower, use_digits,
                                      use_symbols, exclude_similar, exclude_ambiguous)

    entropy = calculate_entropy(password)

    return Response({'password': password, 'entropy': entropy})
