import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kalasetu/app.dart';
import 'package:kalasetu/core/api/mock_api_client.dart';
import 'package:kalasetu/core/api/mock_fixtures.dart';
import 'package:kalasetu/core/localization/app_language.dart';
import 'package:kalasetu/core/media/media_capture_service.dart';
import 'package:kalasetu/features/auth/models/auth_models.dart';
import 'package:kalasetu/features/catalogue/models/catalogue_models.dart';
import 'package:kalasetu/features/dashboard/screens/dashboard_screen.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  testWidgets('switches the login copy between Hindi and English', (
    tester,
  ) async {
    await tester.pumpWidget(KalaSetuApp(apiClient: MockApiClient()));
    await tester.pumpAndSettle();

    expect(find.text('अपने फोन नंबर से जुड़ें'), findsOneWidget);
    await tester.tap(find.text('English'));
    await tester.pump();

    expect(find.text('Continue with your phone'), findsOneWidget);
    expect(find.text('Send OTP'), findsOneWidget);
  });

  testWidgets('completes mock login and reaches dashboard', (tester) async {
    final api = MockApiClient();
    await tester.pumpWidget(KalaSetuApp(apiClient: api));
    await tester.pumpAndSettle();

    await tester.enterText(find.byKey(const Key('phoneField')), '9876543210');
    await tester.tap(find.byKey(const Key('sendOtpButton')));
    await tester.pumpAndSettle();

    expect(find.text('OTP दर्ज करें'), findsOneWidget);
    await tester.enterText(find.byKey(const Key('otpField')), '123456');
    await tester.tap(find.byKey(const Key('verifyOtpButton')));
    await tester.pumpAndSettle();

    expect(find.text('नया उत्पाद जोड़ें'), findsOneWidget);
    expect(find.byKey(const Key('createCatalogueButton')), findsOneWidget);

    await tester.tap(find.byKey(const Key('exploreTab')));
    await tester.pumpAndSettle();
    expect(find.text('कारीगरों के उत्पाद'), findsOneWidget);
    expect(find.text('अभी कोई प्रकाशित कैटलॉग नहीं है'), findsOneWidget);

    await tester.tap(find.text('English'));
    await tester.pump();
    expect(find.text('Explore products'), findsOneWidget);

    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump();
    await tester.pumpWidget(KalaSetuApp(apiClient: api));
    await tester.pumpAndSettle();

    expect(find.text('नया उत्पाद जोड़ें'), findsOneWidget);
    expect(find.byKey(const Key('phoneField')), findsNothing);
  });

  testWidgets('starts the photo-before-voice catalogue flow', (tester) async {
    final api = MockApiClient();
    final profile = MockFixtures.completeProfile();
    final tempDirectory = Directory.systemTemp.createTempSync('kalasetu_test_');
    addTearDown(() => tempDirectory.deleteSync(recursive: true));
    final imageFile =
        File('${tempDirectory.path}${Platform.pathSeparator}product.png')
          ..writeAsBytesSync(
            base64Decode(
              'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
            ),
          );
    const session = AuthSession(
      accessToken: 'mock.jwt.token',
      tokenType: 'bearer',
      expiresInSeconds: 86400,
      user: ArtisanUser(
        id: 'usr_001',
        name: 'Sita Devi',
        phone: '+919876543210',
        role: 'artisan',
        preferredLanguage: 'hi',
      ),
    );

    await tester.pumpWidget(
      MaterialApp(
        home: DashboardScreen(
          apiClient: api,
          session: session,
          profile: profile,
          language: AppLanguage.hindi,
          onLanguageChanged: (_) {},
          onLogout: () {},
          mediaCaptureService: _FakeMediaCaptureService(imageFile.path),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('फोटो लें, फिर हिंदी में बताएं'), findsOneWidget);
    await tester.tap(find.byKey(const Key('createCatalogueButton')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('वस्त्र'));
    await tester.pumpAndSettle();

    expect(find.text('उत्पाद को साफ़ रोशनी में रखें'), findsOneWidget);
    await tester.tap(find.byKey(const Key('capturePhotoButton')));
    await tester.pumpAndSettle();
    expect(find.text('फोटो देखें'), findsOneWidget);

    await tester.tap(find.byKey(const Key('continueFromPhotoButton')));
    await tester.pumpAndSettle();
    expect(find.text('हिंदी में बताएं'), findsOneWidget);
    expect(find.byKey(const Key('voiceRecordButton')), findsOneWidget);

    await tester.pageBack();
    await tester.pumpAndSettle();
    expect(find.text('फोटो देखें'), findsOneWidget);
    expect(find.byKey(const Key('continueFromPhotoButton')), findsOneWidget);
  });
}

class _FakeMediaCaptureService implements MediaCaptureService {
  _FakeMediaCaptureService(this.imagePath);

  final String imagePath;

  @override
  Future<void> cancelVoiceRecording() async {}

  @override
  Future<LocalMediaFile> createDemoPhoto() async =>
      LocalMediaFile(path: imagePath, mimeType: 'image/png');

  @override
  Future<LocalMediaFile?> capturePhoto() async =>
      LocalMediaFile(path: imagePath, mimeType: 'image/jpeg');

  @override
  Future<LocalMediaFile?> pickPhoto() => capturePhoto();

  @override
  Future<void> startVoiceRecording() async {}

  @override
  Future<LocalMediaFile?> stopVoiceRecording() async =>
      const LocalMediaFile(path: 'mock-voice.m4a', mimeType: 'audio/mp4');
}
