import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../../features/auth/models/auth_models.dart';

class SessionStore {
  static const _key = 'kalasetu.auth_session';

  Future<AuthSession?> read() async {
    final preferences = await SharedPreferences.getInstance();
    final value = preferences.getString(_key);
    if (value == null) return null;
    try {
      return AuthSession.fromJson(
        (jsonDecode(value) as Map).cast<String, Object?>(),
      );
    } on FormatException {
      await preferences.remove(_key);
      return null;
    }
  }

  Future<void> save(AuthSession session) async {
    final preferences = await SharedPreferences.getInstance();
    await preferences.setString(_key, jsonEncode(session.toJson()));
  }

  Future<void> clear() async {
    final preferences = await SharedPreferences.getInstance();
    await preferences.remove(_key);
  }
}
