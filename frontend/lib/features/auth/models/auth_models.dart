class OtpRequest {
  const OtpRequest({required this.phone});

  final String phone;

  Map<String, Object?> toJson() => {'phone': phone};
}

class OtpRequestResponse {
  const OtpRequestResponse({
    required this.requestId,
    required this.expiresInSeconds,
    required this.retryAfterSeconds,
  });

  final String requestId;
  final int expiresInSeconds;
  final int retryAfterSeconds;

  factory OtpRequestResponse.fromJson(Map<String, Object?> json) {
    return OtpRequestResponse(
      requestId: json['request_id']! as String,
      expiresInSeconds: json['expires_in_seconds']! as int,
      retryAfterSeconds: json['retry_after_seconds']! as int,
    );
  }
}

class OtpVerification {
  const OtpVerification({required this.requestId, required this.otp});

  final String requestId;
  final String otp;

  Map<String, Object?> toJson() => {'request_id': requestId, 'otp': otp};
}

class ArtisanUser {
  const ArtisanUser({
    required this.id,
    required this.name,
    required this.phone,
    required this.role,
    required this.preferredLanguage,
  });

  final String id;
  final String name;
  final String phone;
  final String role;
  final String preferredLanguage;

  factory ArtisanUser.fromJson(Map<String, Object?> json) {
    return ArtisanUser(
      id: json['id']! as String,
      name: json['name']! as String,
      phone: json['phone']! as String,
      role: json['role']! as String,
      preferredLanguage: json['preferred_language']! as String,
    );
  }
}

class AuthSession {
  const AuthSession({
    required this.accessToken,
    required this.tokenType,
    required this.expiresInSeconds,
    required this.user,
  });

  final String accessToken;
  final String tokenType;
  final int expiresInSeconds;
  final ArtisanUser user;

  factory AuthSession.fromJson(Map<String, Object?> json) {
    return AuthSession(
      accessToken: json['access_token']! as String,
      tokenType: json['token_type']! as String,
      expiresInSeconds: json['expires_in_seconds']! as int,
      user: ArtisanUser.fromJson(json['user']! as Map<String, Object?>),
    );
  }
}
