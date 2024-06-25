from django.shortcuts import render, get_object_or_404
from django.contrib.auth.models import User
from django.db.models import Q
from rest_framework import viewsets, status
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from users.models import FriendRequest
from users.serializer import LoginSerializer, UserSerializer, FriendRequestSerializer


class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing users.
    """

    queryset = User.objects.all().order_by('id') 
    serializer_class = UserSerializer

    def get_queryset(self):
        """
        Custom queryset filter based on search keyword in email, first name, or last name.
        """
        search_keyword = self.request.query_params.get('search', None)
        print("search_keyword", search_keyword)
        if search_keyword:
            self.queryset = self.queryset.filter(
                Q(email__icontains=search_keyword) | 
                Q(first_name__icontains=search_keyword) | 
                Q(last_name__icontains=search_keyword)
            )
        return self.queryset
        
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def login(self, request):
        """
        User login endpoint. Returns a token upon successful authentication.
        """
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data
            refresh = RefreshToken.for_user(user)
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def get_permissions(self):
        """
        Custom permission classes based on action.
        """
        if self.action in ["create", "login"]:
            return [AllowAny()]
        else:
            return [IsAuthenticated()]


class FriendRequestViewSet(viewsets.ModelViewSet):
    queryset = FriendRequest.objects.all()
    serializer_class = FriendRequestSerializer

    @action(detail=False, methods=['post'])
    def send_request(self, request):
        """
        Endpoint to send a friend request from current user to another user.
        Rate-limits requests to 3 per minute.
        """
        try:
            # Check rate limit
            if FriendRequest.objects.filter(from_user=request.user, status='pending').count() >= 3:
                return Response({'error': 'Rate limit exceeded'}, status=status.HTTP_429_TOO_MANY_REQUESTS)
            
            # Get recipient user ID from request data
            to_user_id = request.data.get('to_user_id')
            # Retrieve the recipient user object
            to_user = get_object_or_404(User, id=to_user_id)
            
            # Create or get existing friend request
            friend_request, created = FriendRequest.objects.get_or_create(from_user=request.user, to_user=to_user)
            
            # Check if the request was already sent
            if not created:
                return Response({'error': 'Friend request already sent'}, status=status.HTTP_400_BAD_REQUEST)
            
            return Response(self.get_serializer(friend_request).data, status=status.HTTP_201_CREATED)
        
        except User.DoesNotExist:
            return Response({'error': 'User with the provided ID does not exist'}, status=status.HTTP_404_NOT_FOUND)
        
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def accept_request(self, request):
        """
        Endpoint to accept a pending friend request.
        """
        try:
            # Get friend request ID from request data
            friend_request_id = request.data.get('request_id')
            # Retrieve the friend request object if exists for current user
            friend_request = get_object_or_404(FriendRequest, id=friend_request_id)
            # Update status to accepted
            friend_request.status = 'accepted'
            friend_request.save()
            
            return Response({'status': 'accepted'})
        
        except FriendRequest.DoesNotExist:
            return Response({'error': 'Friend request not found'}, status=status.HTTP_404_NOT_FOUND)
        
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def reject_request(self, request):
        """
        Endpoint to reject a pending friend request.
        """
        try:
            # Get friend request ID from request data
            friend_request_id = request.data.get('request_id')
            # Retrieve the friend request object if exists for current user
            friend_request = get_object_or_404(FriendRequest, id=friend_request_id)
            
            # Update status to rejected
            friend_request.status = 'rejected'
            friend_request.save()
            
            return Response({'status': 'rejected'})
        
        except FriendRequest.DoesNotExist:
            return Response({'error': 'Friend request not found'}, status=status.HTTP_404_NOT_FOUND)
        
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def list_friends(self, request):
        """
        Endpoint to list friends of the current user (users who accepted friend requests).
        """
        try:
            # Query for users who are friends (accepted requests)
            friends = User.objects.filter(
                Q(sent_requests__to_user=request.user, sent_requests__status='accepted') |
                Q(received_requests__from_user=request.user, received_requests__status='accepted')
            )
            
            # Paginate results if applicable
            page = self.paginate_queryset(friends)
            if page is not None:
                serializer = UserSerializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = UserSerializer(friends, many=True)
            return Response(serializer.data)
        
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def list_pending_requests(self, request):
        """
        Endpoint to list pending friend requests received by the current user.
        """
        try:
            # Query for pending friend requests
            pending_requests = FriendRequest.objects.filter(to_user=request.user, status='pending')
            
            # Paginate results if applicable
            page = self.paginate_queryset(pending_requests)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.get_serializer(pending_requests, many=True)
            return Response(serializer.data)
        
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        