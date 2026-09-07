from pathlib import Path

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.clubs.api.permissions import CanAccessTeamMembers
from apps.clubs.api.schema import (
    ADMIN_CLUB_AVAILABLE_OWNERS_SCHEMA,
    ADMIN_CLUB_CREATE_SCHEMA,
    ADMIN_CLUB_LIST_SCHEMA,
    ADMIN_CLUB_RETRIEVE_SCHEMA,
    CLUB_ID_DOCUMENT_SCHEMA,
    MY_CLUB_SCHEMA,
    MY_CLUB_UPDATE_SCHEMA,
    TEAM_CREATE_SCHEMA,
    TEAM_DELETE_SCHEMA,
    TEAM_LIST_SCHEMA,
    TEAM_RETRIEVE_SCHEMA,
    TEAM_UPDATE_SCHEMA,
)
from apps.clubs.api.serializers import (
    AdminClubCreateSerializer,
    AvailableOwnerSerializer,
    ClubSerializer,
    ClubUpdateSerializer,
    TeamMemberCreateSerializer,
    TeamMemberSerializer,
    TeamMemberUpdateSerializer,
)
from apps.clubs.models import Club, TeamMember
from apps.clubs.services import authorization
from apps.users.api.permissions import IsPlatformAdmin
from apps.users.constants import Role

User = get_user_model()


class MyClubView(RetrieveUpdateAPIView):
    """The club owned by the authenticated user."""

    serializer_class = ClubSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    http_method_names = ["get", "patch", "head", "options"]

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return ClubUpdateSerializer
        return ClubSerializer

    def get_object(self):
        club = authorization.get_owned_club(self.request.user)
        if club is None:
            raise NotFound("You do not own a club.")
        return club

    @swagger_auto_schema(**MY_CLUB_SCHEMA)
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(**MY_CLUB_UPDATE_SCHEMA)
    def patch(self, request, *args, **kwargs):
        club = self.get_object()
        if not authorization.can_edit_club(request.user, club):
            raise PermissionDenied("You cannot edit this club.")
        serializer = self.get_serializer(club, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        club.refresh_from_db()
        return Response(ClubSerializer(club).data)


class ClubIdDocumentView(APIView):
    """Download a club's owner identity document.

    The file is stored outside the public media tree, so this view is
    the only way to reach it and it checks permissions first.
    """

    @swagger_auto_schema(**CLUB_ID_DOCUMENT_SCHEMA)
    def get(self, request, pk):
        club = get_object_or_404(Club, pk=pk)
        if not authorization.can_read_club_documents(request.user, club):
            raise PermissionDenied("You cannot access this document.")
        if not club.owner_id_document:
            raise NotFound("No identity document has been uploaded.")
        return FileResponse(
            club.owner_id_document.open("rb"),
            as_attachment=True,
            filename=Path(club.owner_id_document.name).name,
        )


class AdminClubViewSet(viewsets.ModelViewSet):
    """Club administration. Restricted to Platform Admin."""

    queryset = Club.objects.select_related("owner").all()
    permission_classes = [IsPlatformAdmin]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["name", "owner__email"]
    ordering_fields = ["created_at", "name"]
    ordering = ["-created_at"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    FILTER_FIELDS = ("entity_type", "base_region", "status")
    BOOLEAN_FILTER_FIELDS = ("identity_verified", "payment_verified")

    def get_serializer_class(self):
        if self.action == "create":
            return AdminClubCreateSerializer
        return ClubSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        for field in self.FILTER_FIELDS:
            value = params.get(field)
            if value:
                qs = qs.filter(**{field: value})
        for field in self.BOOLEAN_FILTER_FIELDS:
            value = params.get(field)
            if value in ("true", "false"):
                qs = qs.filter(**{field: value == "true"})
        return qs

    @swagger_auto_schema(**ADMIN_CLUB_LIST_SCHEMA)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(**ADMIN_CLUB_RETRIEVE_SCHEMA)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(**ADMIN_CLUB_CREATE_SCHEMA)
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        club = serializer.save()
        return Response(
            ClubSerializer(club).data, status=status.HTTP_201_CREATED
        )

    @swagger_auto_schema(**ADMIN_CLUB_AVAILABLE_OWNERS_SCHEMA)
    @action(detail=False, url_path="available-owners", pagination_class=None)
    def available_owners(self, request):
        """Club owners still free to be assigned a club.

        ``club`` is one-to-one, so an owner who already has one cannot
        take another; this is what the create form's owner picker lists.
        Returned unpaginated: an owner leaves the set as soon as they are
        given a club, so it only ever holds the current backlog.
        """
        owners = User.objects.filter(
            role=Role.CLUB_OWNER, is_active=True, club__isnull=True
        ).order_by("full_name", "email")

        search = request.query_params.get("search")
        if search:
            owners = owners.filter(
                Q(email__icontains=search) | Q(full_name__icontains=search)
            )

        return Response(AvailableOwnerSerializer(owners, many=True).data)


class TeamMemberViewSet(viewsets.ModelViewSet):
    """Club staff management, scoped to the requester's club."""

    queryset = TeamMember.objects.select_related("club", "user").prefetch_related(
        "certificates"
    )
    permission_classes = [CanAccessTeamMembers]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["user__email", "user__full_name"]
    ordering_fields = ["created_at", "user__email", "user__full_name"]
    ordering = ["-created_at"]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_serializer_class(self):
        if self.action == "create":
            return TeamMemberCreateSerializer
        if self.action == "partial_update":
            return TeamMemberUpdateSerializer
        return TeamMemberSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.action == "create":
            context["club"] = self._club_for_write()
        return context

    def _club_for_write(self):
        """The club a create/update acts on."""
        club = authorization.get_owned_club(self.request.user)
        if club is None:
            # Platform admins do not own a club; they must say which one.
            club_id = self.request.data.get("club")
            club = Club.objects.filter(pk=club_id).first() if club_id else None
            if club is None:
                raise PermissionDenied(
                    "Specify a club to add this team member to."
                )
        if not authorization.can_manage_team(self.request.user, club):
            raise PermissionDenied("You cannot manage this club's team.")
        return club

    def get_queryset(self):
        qs = super().get_queryset()
        scope = authorization.readable_club_scope(self.request.user)
        if scope is None:
            return qs.none()
        if scope is not authorization.ALL_CLUBS:
            return qs.filter(club=scope)
        club_id = self.request.query_params.get("club")
        if club_id:
            qs = qs.filter(club_id=club_id)
        return qs

    @swagger_auto_schema(**TEAM_LIST_SCHEMA)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(**TEAM_RETRIEVE_SCHEMA)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(**TEAM_CREATE_SCHEMA)
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        member = serializer.save()
        return Response(
            TeamMemberSerializer(member).data,
            status=status.HTTP_201_CREATED,
        )

    @swagger_auto_schema(**TEAM_UPDATE_SCHEMA)
    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        instance.refresh_from_db()
        return Response(TeamMemberSerializer(instance).data)

    @swagger_auto_schema(**TEAM_DELETE_SCHEMA)
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self._deactivate(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @staticmethod
    @transaction.atomic
    def _deactivate(member):
        """Soft delete: never remove the membership or the account."""
        if member.is_active:
            member.is_active = False
            member.save(update_fields=["is_active", "updated_at"])
        if member.user.is_active:
            member.user.is_active = False
            member.user.save(update_fields=["is_active", "updated_at"])
