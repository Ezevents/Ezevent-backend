from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from django.contrib.auth import get_user_model
from .models import Users, Role, UserRole
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt import serializers as jwt_serializers, exceptions as jwt_exceptions
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken

class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ['id', 'name']

class UserRoleSerializer(serializers.ModelSerializer):
    role = RoleSerializer()  

    class Meta:
        model = UserRole
        fields = ['user', 'role']

class UserSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField()
    email = serializers.EmailField()
    firstname = serializers.CharField(max_length=100)
    lastname = serializers.CharField(max_length=100)
    password = serializers.CharField(max_length=100, write_only=True)
    contact = serializers.CharField(max_length=15, allow_blank=True, required=False)
    profile_pic = serializers.CharField(max_length=500, allow_blank=True, required=False)
    created_at = serializers.DateTimeField(read_only=True)
    role = serializers.CharField(source='userrole.role.name', read_only=True)

    class Meta:
        model = Users
        fields = ['id', 'email', 'firstname', 'lastname', 'contact', 'profile_pic', 'password', 'created_at', 'role']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        profile_pic = validated_data.get('profile_pic', None)

        user = Users(
            email=validated_data['email'],
            firstname=validated_data['firstname'],
            lastname=validated_data['lastname'],
            contact=validated_data.get('contact', ''),
            profile_pic=profile_pic or "https://firebasestorage.googleapis.com/v0/b/happy-hoe.appspot.com/o/dev%2FprofilePic%2F1724404221671_default-user-profile.png?alt=media&token=0793e28f-0230-46ef-abc0-2ea73ebd6fd4"
        )
        user.set_password(validated_data['password'])
        user.save()
        return user

    def update(self, instance, validated_data):
        instance.email = validated_data.get('email', instance.email)
        instance.firstname = validated_data.get('firstname', instance.firstname)
        instance.lastname = validated_data.get('lastname', instance.lastname)
        instance.contact = validated_data.get('contact', instance.contact)
        instance.profile_pic = validated_data.get('profile_pic', instance.profile_pic)  # Keep existing if not updated
        if 'password' in validated_data:
            instance.set_password(validated_data['password'])
        instance.save()
        return instance
        
    def get_role(self, obj):
        user_role = UserRole.objects.filter(user=obj).first()
        return user_role.role.name if user_role else None
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        user_role = UserRole.objects.filter(user=instance).first()
        # Assigning "admin" if role is None
        representation['role'] = user_role.role.name if user_role else "admin"
        return representation

class CookieTokenRefreshSerializer(jwt_serializers.TokenRefreshSerializer):
    refresh = None

    def validate(self, attrs):
        attrs['refresh'] = self.context['request'].COOKIES.get('refresh')
        if not attrs['refresh']:
            raise jwt_exceptions.InvalidToken(
                'No valid token found in cookie \'refresh\''
            )

        data = super().validate(attrs)

        refresh = RefreshToken(attrs['refresh'])

        user_id = refresh.get('user_id')

        user = Users.objects.get(id=user_id)

        user_role = UserRole.objects.filter(user=user).first()
        role_name = user_role.role.name if user_role else 'admin'

        access_token = refresh.access_token
        access_token['role'] = role_name  

        data['access'] = str(access_token)

        return data