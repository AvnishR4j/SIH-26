import 'app_language.dart';

class AppStrings {
  const AppStrings(this.language);

  final AppLanguage language;

  bool get isHindi => language == AppLanguage.hindi;

  String get connectTitle =>
      isHindi ? 'अपने फोन नंबर से जुड़ें' : 'Continue with your phone';
  String get otpSubtitle =>
      isHindi ? 'हम आपको एक OTP भेजेंगे' : 'We’ll send you an OTP';
  String get phoneLabel => isHindi ? 'फोन नंबर' : 'Phone number';
  String get sendOtp => isHindi ? 'OTP भेजें' : 'Send OTP';
  String get terms => isHindi
      ? 'जारी रखकर आप हमारी सेवा शर्तों से सहमत होते हैं'
      : 'By continuing, you agree to our terms of service';
  String get invalidPhone => isHindi
      ? 'कृपया 10 अंकों का सही फोन नंबर डालें'
      : 'Enter a valid 10-digit phone number';
  String get genericError => isHindi
      ? 'कुछ गलत हुआ। कृपया दोबारा कोशिश करें।'
      : 'Something went wrong. Please try again.';
  String get verifyTitle => isHindi ? 'OTP दर्ज करें' : 'Enter OTP';
  String otpSentTo(String phone) => isHindi
      ? '$phone पर भेजा गया 6 अंकों का कोड डालें'
      : 'Enter the 6-digit code sent to $phone';
  String get otpLabel => isHindi ? '6 अंकों का OTP' : '6-digit OTP';
  String get verifyOtp => isHindi ? 'OTP सत्यापित करें' : 'Verify OTP';
  String get invalidOtp =>
      isHindi ? 'कृपया 6 अंकों का OTP डालें' : 'Enter the 6-digit OTP';
  String get resendOtp => isHindi ? 'OTP दोबारा भेजें' : 'Resend OTP';
  String resendIn(int seconds) => isHindi
      ? '$seconds सेकंड में दोबारा भेजें'
      : 'Resend in $seconds seconds';
  String get mockOtpHint => isHindi ? 'डेमो OTP: 123456' : 'Demo OTP: 123456';
  String greeting(String name) => isHindi ? 'नमस्ते, $name' : 'Hello, $name';
  String get addProduct => isHindi ? 'नया उत्पाद जोड़ें' : 'Add a new product';
  String get createCatalogue => isHindi ? 'कैटलॉग बनाएं' : 'Create catalogue';
  String get catalogueVoiceCue => isHindi
      ? 'फोटो लें, फिर हिंदी में बताएं'
      : 'Take a photo, then describe it in Hindi';
  String get photoAndVoice =>
      isHindi ? 'फोटो और आवाज़ से' : 'With photo and voice';
  String get recentDrafts => isHindi ? 'हाल के कैटलॉग' : 'Recent catalogues';
  String get noDrafts =>
      isHindi ? 'अभी कोई ड्राफ्ट नहीं है' : 'You don’t have any drafts yet';
  String get firstCatalogue => isHindi
      ? 'अपना पहला उत्पाद कैटलॉग बनाएं'
      : 'Create your first product catalogue';
  String get categoryQuestion =>
      isHindi ? 'किस शिल्प का उत्पाद है?' : 'Which craft is this product?';
  String categoryLabel(String category) => switch (category) {
    'textile' => isHindi ? 'वस्त्र' : 'Textile',
    'embroidery' => isHindi ? 'कढ़ाई' : 'Embroidery',
    _ => category,
  };
  String get newCatalogue => isHindi ? 'नया कैटलॉग' : 'New catalogue';
  String draftStatus(String status) => switch (status) {
    'draft' => isHindi ? 'फोटो या आवाज़ बाकी है' : 'Photo or voice pending',
    'media_ready' => isHindi ? 'बनाने के लिए तैयार' : 'Ready to generate',
    'processing' => isHindi ? 'कैटलॉग बन रही है' : 'Generating catalogue',
    'needs_confirmation' =>
      isHindi ? 'समीक्षा के लिए तैयार' : 'Ready for review',
    'ready_for_approval' =>
      isHindi ? 'मंज़ूरी के लिए तैयार' : 'Ready for approval',
    'approved' => isHindi ? 'मंज़ूर' : 'Approved',
    'failed' => isHindi ? 'फिर कोशिश करें' : 'Try again',
    _ => status,
  };
  String get nextStepSoon => isHindi
      ? 'उत्पाद फोटो स्क्रीन अगली समीक्षा में जोड़ी जाएगी'
      : 'The product photo screen will be added in the next review';

  String get productPhoto => isHindi ? 'उत्पाद की फोटो' : 'Product photo';
  String get photoLighting => isHindi
      ? 'उत्पाद को साफ़ रोशनी में रखें'
      : 'Place the product in clear light';
  String get photoFraming => isHindi
      ? 'पूरा उत्पाद फ्रेम में दिखना चाहिए।'
      : 'Make sure the whole product is visible in the frame.';
  String get chooseFromGallery =>
      isHindi ? 'गैलरी से चुनें' : 'Choose from gallery';
  String get takePhoto => isHindi ? 'फोटो लें' : 'Take photo';
  String get useDemoPhoto =>
      isHindi ? 'डेमो फोटो इस्तेमाल करें' : 'Use demo photo';
  String get reviewPhoto => isHindi ? 'फोटो देखें' : 'Review photo';
  String get retake => isHindi ? 'दोबारा लें' : 'Retake';
  String get continueLabel => isHindi ? 'आगे बढ़ें' : 'Continue';
  String get photoCaptureFailed =>
      isHindi ? 'फोटो नहीं लिया जा सका।' : 'The photo could not be captured.';
  String get demoPhotoFailed => isHindi
      ? 'डेमो फोटो नहीं बनाई जा सकी।'
      : 'The demo photo could not be created.';
  String get mediaConsentTitle =>
      isHindi ? 'मीडिया प्रोसेसिंग की सहमति' : 'Media processing consent';
  String get mediaConsentBody => isHindi
      ? 'फोटो सुधारने और आवाज़ से कैटलॉग बनाने के लिए आपकी स्पष्ट सहमति चाहिए। मूल फोटो हमेशा सुरक्षित रहेगा।'
      : 'We need your consent to enhance the photo and create a catalogue from your voice. Your original photo will remain safe.';
  String get consentAgree => isHindi ? 'मैं सहमत हूं' : 'I agree';
  String get notNow => isHindi ? 'अभी नहीं' : 'Not now';
  String get photoTooLarge =>
      isHindi ? 'फोटो 10 MB से छोटा रखें।' : 'Keep the photo under 10 MB.';
  String get unsupportedPhoto => isHindi
      ? 'JPEG, PNG या WebP फोटो चुनें।'
      : 'Choose a JPEG, PNG, or WebP photo.';
  String get photoStorageFailed => isHindi
      ? 'फोटो सुरक्षित नहीं हो सका। फिर कोशिश करें।'
      : 'The photo could not be saved. Try again.';
  String get photoUploadFailed => isHindi
      ? 'फोटो अपलोड नहीं हो सका। फिर कोशिश करें।'
      : 'The photo could not be uploaded. Try again.';

  String get productDescription =>
      isHindi ? 'उत्पाद का वर्णन' : 'Product description';
  String get describeInHindi =>
      isHindi ? 'हिंदी में बताएं' : 'Describe it in Hindi';
  String get descriptionExample => isHindi
      ? 'जैसे: यह क्या है, किस चीज़ से बना है, रंग, नाप'
      : 'For example: what it is, what it is made of, colour, and size';
  String get stopRecording => isHindi ? 'रिकॉर्डिंग रोकें' : 'Stop recording';
  String get record => isHindi ? 'रिकॉर्ड करें' : 'Record';
  String get stopWhenDone => isHindi
      ? 'बोलना पूरा हो तो रोकें'
      : 'Stop when you have finished speaking';
  String get voiceRecorded =>
      isHindi ? 'आपकी आवाज़ रिकॉर्ड हो गई है' : 'Your voice has been recorded';
  String get tapMicToStart => isHindi
      ? 'माइक दबाकर बोलना शुरू करें'
      : 'Tap the microphone to start speaking';
  String get recordAgain => isHindi ? 'दोबारा रिकॉर्ड करें' : 'Record again';
  String get generateCatalogue =>
      isHindi ? 'कैटलॉग बनाएं' : 'Generate catalogue';
  String get maximumTwoMinutes =>
      isHindi ? 'अधिकतम 2 मिनट' : 'Maximum 2 minutes';
  String get voiceConsentTitle =>
      isHindi ? 'आपकी सहमति चाहिए' : 'Your consent is required';
  String get voiceConsentBody => isHindi
      ? 'आवाज़ से कैटलॉग बनाने के लिए मीडिया प्रोसेसिंग की अनुमति दें। आपकी रिकॉर्डिंग निजी ड्राफ्ट से जुड़ी रहेगी।'
      : 'Allow media processing to create a catalogue from your voice. Your recording will remain linked to your private draft.';
  String get microphonePermission => isHindi
      ? 'रिकॉर्ड करने के लिए माइक्रोफोन की अनुमति दें।'
      : 'Allow microphone access to record.';
  String get recordingStartFailed => isHindi
      ? 'रिकॉर्डिंग शुरू नहीं हो सकी।'
      : 'Recording could not be started.';
  String get recordingSaveFailed => isHindi
      ? 'रिकॉर्डिंग सुरक्षित नहीं हो सकी।'
      : 'The recording could not be saved.';
  String get recordingTooLarge => isHindi
      ? 'रिकॉर्डिंग 25 MB से छोटी रखें।'
      : 'Keep the recording under 25 MB.';
  String get unsupportedRecording => isHindi
      ? 'M4A, MP3, WAV या WebM रिकॉर्डिंग चुनें।'
      : 'Choose an M4A, MP3, WAV, or WebM recording.';
  String get generationUnavailable => isHindi
      ? 'अभी कैटलॉग नहीं बन सकी। आपकी रिकॉर्डिंग सुरक्षित है।'
      : 'The catalogue could not be generated now. Your recording is safe.';
  String get recordingUploadFailed => isHindi
      ? 'रिकॉर्डिंग अपलोड नहीं हो सकी। फिर कोशिश करें।'
      : 'The recording could not be uploaded. Try again.';

  String get generatingCatalogue =>
      isHindi ? 'कैटलॉग तैयार हो रही है' : 'Generating catalogue';
  String get catalogueReady =>
      isHindi ? 'आपकी कैटलॉग तैयार है' : 'Your catalogue is ready';
  String get readyForReview => isHindi
      ? 'ड्राफ्ट सुरक्षित है और समीक्षा के लिए तैयार है।'
      : 'The draft is saved and ready for review.';
  String get generationFailed => isHindi
      ? 'कैटलॉग अभी नहीं बन सकी। फोटो और आवाज़ सुरक्षित हैं।'
      : 'The catalogue could not be generated yet. Your photo and voice are safe.';
  String get connectionFailed => isHindi
      ? 'कनेक्शन नहीं हो सका। आपका काम सुरक्षित है।'
      : 'Could not connect. Your work is safe.';
  String get retryFailed => isHindi
      ? 'फिर कोशिश नहीं हो सकी। आपका काम सुरक्षित है।'
      : 'Could not retry. Your work is safe.';
  String get tryAgain => isHindi ? 'फिर कोशिश करें' : 'Try again';
  String get workContinues => isHindi ? 'काम जारी है' : 'Work is continuing';
  String get reopenDraftLater => isHindi
      ? 'आप बाद में इस ड्राफ्ट को फिर खोल सकते हैं।'
      : 'You can reopen this draft later.';
  String get catalogueBeingPrepared => isHindi
      ? 'आपकी कैटलॉग तैयार की जा रही है'
      : 'Your catalogue is being prepared';
  String get bilingualDescription => isHindi
      ? 'फोटो और आवाज़ से हिंदी और English विवरण बनाया जा रहा है।'
      : 'Hindi and English descriptions are being created from your photo and voice.';
  String get goHome => isHindi ? 'होम पर जाएं' : 'Go to home';
  String get viewLater => isHindi ? 'बाद में देखें' : 'View later';

  String get profileAndConsent =>
      isHindi ? 'प्रोफ़ाइल और सहमति' : 'Profile and consent';
  String get profileIntro =>
      isHindi ? 'बस थोड़ी-सी जानकारी' : 'Just a few details';
  String get profileIntroBody => isHindi
      ? 'इससे आपका निजी ड्राफ्ट सही शिल्प श्रेणी में बनेगा।'
      : 'This helps place your private draft in the right craft category.';
  String get nameLabel => isHindi ? 'नाम' : 'Name';
  String get clusterLabel => isHindi ? 'समूह / क्लस्टर' : 'Group / cluster';
  String get craftCategoryLabel => isHindi ? 'शिल्प श्रेणी' : 'Craft category';
  String get craftCategoryHint =>
      isHindi ? 'जैसे textile, embroidery' : 'For example, textile, embroidery';
  String get aiConsentLabel => isHindi
      ? 'मैं फोटो और आवाज़ की AI प्रोसेसिंग के लिए सहमत हूं।'
      : 'I consent to AI processing of my photos and voice.';
  String get aiConsentDetails => isHindi
      ? 'मूल फोटो सुरक्षित रखा जाएगा। सहमति बाद में वापस ली जा सकती है।'
      : 'The original photo will be kept safe. You can withdraw consent later.';
  String get completeProfileError => isHindi
      ? 'कृपया सभी जानकारी भरें और सहमति दें।'
      : 'Complete all fields and provide consent.';
  String get saveAndContinue =>
      isHindi ? 'सहेजें और आगे बढ़ें' : 'Save and continue';
  String get profileLoadFailed => isHindi
      ? 'प्रोफ़ाइल लोड नहीं हो सकी।'
      : 'The profile could not be loaded.';
}
