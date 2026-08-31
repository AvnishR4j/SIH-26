import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../core/api/api_client.dart';
import '../../../core/localization/app_language.dart';
import '../../../core/localization/app_strings.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/auth_shell.dart';
import '../models/auth_models.dart';
import 'otp_screen.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({
    super.key,
    required this.apiClient,
    required this.language,
    required this.onLanguageChanged,
    required this.onAuthenticated,
  });

  final ApiClient apiClient;
  final AppLanguage language;
  final ValueChanged<AppLanguage> onLanguageChanged;
  final Future<void> Function(AuthSession session) onAuthenticated;

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _phoneController = TextEditingController();
  String? _error;
  bool _isLoading = false;
  String? _idempotencyKey;

  @override
  void dispose() {
    _phoneController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final strings = AppStrings(widget.language);
    final digits = _phoneController.text.replaceAll(RegExp(r'\D'), '');
    if (digits.length != 10) {
      setState(() => _error = strings.invalidPhone);
      return;
    }

    setState(() {
      _error = null;
      _isLoading = true;
      _idempotencyKey ??= _newUuid();
    });

    try {
      final phone = '+91$digits';
      final response = await widget.apiClient.requestOtp(
        OtpRequest(phone: phone),
        idempotencyKey: _idempotencyKey!,
      );
      if (!mounted) return;
      await Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => OtpScreen(
            apiClient: widget.apiClient,
            phone: phone,
            otpRequest: response,
            language: widget.language,
            onLanguageChanged: widget.onLanguageChanged,
            onAuthenticated: widget.onAuthenticated,
          ),
        ),
      );
      _idempotencyKey = null;
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } catch (_) {
      if (mounted) setState(() => _error = strings.genericError);
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  String _newUuid() {
    final random = Random.secure();
    final bytes = List<int>.generate(16, (_) => random.nextInt(256));
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    final hex = bytes
        .map((byte) => byte.toRadixString(16).padLeft(2, '0'))
        .join();
    return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-'
        '${hex.substring(12, 16)}-${hex.substring(16, 20)}-${hex.substring(20)}';
  }

  @override
  Widget build(BuildContext context) {
    final strings = AppStrings(widget.language);
    return AuthShell(
      language: widget.language,
      onLanguageChanged: widget.onLanguageChanged,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            strings.connectTitle,
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const SizedBox(height: 4),
          Text(
            strings.otpSubtitle,
            style: Theme.of(context).textTheme.bodyMedium,
          ),
          const SizedBox(height: 22),
          Text(
            strings.phoneLabel,
            style: const TextStyle(color: AppColors.mutedText),
          ),
          const SizedBox(height: 7),
          TextField(
            key: const Key('phoneField'),
            controller: _phoneController,
            keyboardType: TextInputType.phone,
            textInputAction: TextInputAction.done,
            inputFormatters: [
              FilteringTextInputFormatter.digitsOnly,
              LengthLimitingTextInputFormatter(10),
            ],
            decoration: InputDecoration(
              prefixIcon: const Padding(
                padding: EdgeInsets.only(left: 14, right: 11),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      '+91',
                      style: TextStyle(
                        color: AppColors.text,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    SizedBox(width: 11),
                    SizedBox(
                      height: 22,
                      child: VerticalDivider(width: 1, color: AppColors.border),
                    ),
                  ],
                ),
              ),
              hintText: '98765 43210',
              errorText: _error,
            ),
            onSubmitted: (_) {
              if (!_isLoading) _submit();
            },
          ),
          const SizedBox(height: 20),
          FilledButton(
            key: const Key('sendOtpButton'),
            onPressed: _isLoading ? null : _submit,
            child: _isLoading
                ? const SizedBox.square(
                    dimension: 22,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Colors.white,
                    ),
                  )
                : Text(strings.sendOtp),
          ),
          const SizedBox(height: 18),
          Text(
            strings.terms,
            textAlign: TextAlign.center,
            style: const TextStyle(color: AppColors.mutedText, fontSize: 11.5),
          ),
        ],
      ),
    );
  }
}
