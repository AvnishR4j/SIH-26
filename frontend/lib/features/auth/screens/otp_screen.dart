import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../core/api/api_client.dart';
import '../../../core/localization/app_language.dart';
import '../../../core/localization/app_strings.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/auth_shell.dart';
import '../models/auth_models.dart';

class OtpScreen extends StatefulWidget {
  const OtpScreen({
    super.key,
    required this.apiClient,
    required this.phone,
    required this.otpRequest,
    required this.language,
    required this.onLanguageChanged,
    required this.onAuthenticated,
  });

  final ApiClient apiClient;
  final String phone;
  final OtpRequestResponse otpRequest;
  final AppLanguage language;
  final ValueChanged<AppLanguage> onLanguageChanged;
  final Future<void> Function(AuthSession session) onAuthenticated;

  @override
  State<OtpScreen> createState() => _OtpScreenState();
}

class _OtpScreenState extends State<OtpScreen> {
  final _otpController = TextEditingController();
  late OtpRequestResponse _otpRequest;
  Timer? _timer;
  int _secondsRemaining = 0;
  bool _isLoading = false;
  String? _error;
  String? _resendIdempotencyKey;
  late AppLanguage _language;

  @override
  void initState() {
    super.initState();
    _otpRequest = widget.otpRequest;
    _language = widget.language;
    _startCountdown(_otpRequest.retryAfterSeconds);
  }

  @override
  void dispose() {
    _timer?.cancel();
    _otpController.dispose();
    super.dispose();
  }

  void _startCountdown(int seconds) {
    _timer?.cancel();
    setState(() => _secondsRemaining = seconds);
    _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (!mounted) return;
      if (_secondsRemaining <= 1) {
        timer.cancel();
        setState(() => _secondsRemaining = 0);
      } else {
        setState(() => _secondsRemaining--);
      }
    });
  }

  Future<void> _verify() async {
    final strings = AppStrings(_language);
    if (_otpController.text.length != 6) {
      setState(() => _error = strings.invalidOtp);
      return;
    }
    setState(() {
      _error = null;
      _isLoading = true;
    });
    try {
      final session = await widget.apiClient.verifyOtp(
        OtpVerification(
          requestId: _otpRequest.requestId,
          otp: _otpController.text,
        ),
      );
      if (!mounted) return;
      await widget.onAuthenticated(session);
      if (mounted) {
        Navigator.of(context).popUntil((route) => route.isFirst);
      }
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } catch (_) {
      if (mounted) setState(() => _error = strings.genericError);
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _resend() async {
    if (_secondsRemaining > 0 || _isLoading) return;
    setState(() => _isLoading = true);
    try {
      final response = await widget.apiClient.requestOtp(
        OtpRequest(phone: widget.phone),
        idempotencyKey: _resendIdempotencyKey ??= _newUuid(),
      );
      if (!mounted) return;
      _otpRequest = response;
      _resendIdempotencyKey = null;
      _startCountdown(response.retryAfterSeconds);
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
    final strings = AppStrings(_language);
    return AuthShell(
      language: _language,
      onLanguageChanged: (language) {
        setState(() => _language = language);
        widget.onLanguageChanged(language);
      },
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            strings.verifyTitle,
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const SizedBox(height: 5),
          Text(
            strings.otpSentTo(widget.phone),
            style: Theme.of(context).textTheme.bodyMedium,
          ),
          const SizedBox(height: 20),
          TextField(
            key: const Key('otpField'),
            controller: _otpController,
            autofocus: true,
            keyboardType: TextInputType.number,
            textInputAction: TextInputAction.done,
            textAlign: TextAlign.center,
            style: const TextStyle(
              fontSize: 22,
              fontWeight: FontWeight.w700,
              letterSpacing: 8,
            ),
            inputFormatters: [
              FilteringTextInputFormatter.digitsOnly,
              LengthLimitingTextInputFormatter(6),
            ],
            decoration: InputDecoration(
              labelText: strings.otpLabel,
              errorText: _error,
            ),
            onSubmitted: (_) {
              if (!_isLoading) _verify();
            },
          ),
          const SizedBox(height: 9),
          Text(
            strings.mockOtpHint,
            textAlign: TextAlign.center,
            style: const TextStyle(
              color: AppColors.darkAccent,
              fontSize: 12,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 18),
          FilledButton(
            key: const Key('verifyOtpButton'),
            onPressed: _isLoading ? null : _verify,
            child: _isLoading
                ? const SizedBox.square(
                    dimension: 22,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Colors.white,
                    ),
                  )
                : Text(strings.verifyOtp),
          ),
          const SizedBox(height: 12),
          TextButton(
            onPressed: _secondsRemaining == 0 ? _resend : null,
            child: Text(
              _secondsRemaining == 0
                  ? strings.resendOtp
                  : strings.resendIn(_secondsRemaining),
            ),
          ),
        ],
      ),
    );
  }
}
