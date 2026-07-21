from rest_framework import serializers
from .models import PasswordEntry, Folder, Category, Tag, Vault, Share


class FolderSerializer(serializers.ModelSerializer):
    entry_count = serializers.SerializerMethodField()

    class Meta:
        model = Folder
        fields = ['id', 'name', 'parent', 'icon', 'color', 'entry_count', 'created_at']
        read_only_fields = ['id', 'created_at']

    def get_entry_count(self, obj):
        return obj.entries.filter(is_deleted=False).count()


class CategorySerializer(serializers.ModelSerializer):
    entry_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'icon', 'color', 'entry_count', 'created_at']

    def get_entry_count(self, obj):
        return obj.entries.filter(is_deleted=False).count()


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name', 'color', 'created_at']


class PasswordEntryListSerializer(serializers.ModelSerializer):
    folder_name = serializers.CharField(source='folder.name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = PasswordEntry
        fields = [
            'id', 'name', 'url', 'folder_name', 'category_name',
            'sensitivity', 'is_favorite', 'is_deleted',
            'last_accessed', 'access_count', 'version',
            'expires_at', 'created_at', 'updated_at',
        ]


class PasswordEntrySerializer(serializers.ModelSerializer):
    username = serializers.SerializerMethodField()
    password = serializers.SerializerMethodField()
    notes = serializers.SerializerMethodField()
    tags = TagSerializer(many=True, read_only=True)

    class Meta:
        model = PasswordEntry
        fields = [
            'id', 'name', 'url', 'username', 'password', 'notes',
            'folder', 'category', 'tags',
            'sensitivity', 'is_favorite', 'is_deleted',
            'last_accessed', 'access_count', 'version',
            'expires_at', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'last_accessed', 'access_count', 'version', 'created_at', 'updated_at']

    def get_username(self, obj):
        return obj.get_username()

    def get_password(self, obj):
        return obj.get_password()

    def get_notes(self, obj):
        return obj.get_notes()


class ShareSerializer(serializers.ModelSerializer):
    class Meta:
        model = Share
        fields = '__all__'
        read_only_fields = ['id', 'shared_by', 'created_at', 'is_revoked', 'revoked_at']


class VaultSerializer(serializers.ModelSerializer):
    password_count = serializers.IntegerField(read_only=True)
    shared_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Vault
        fields = ['id', 'name', 'description', 'password_count', 'shared_count', 'created_at', 'updated_at']
