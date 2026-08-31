package in.kalasetu.kalasetu;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.media.MediaRecorder;
import android.net.Uri;
import android.os.Build;
import android.provider.MediaStore;
import android.webkit.MimeTypeMap;

import androidx.annotation.NonNull;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;
import androidx.core.content.FileProvider;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;

import io.flutter.embedding.android.FlutterActivity;
import io.flutter.embedding.engine.FlutterEngine;
import io.flutter.plugin.common.MethodChannel;

public class MainActivity extends FlutterActivity {
    private static final String CHANNEL_NAME = "in.kalasetu/media";
    private static final String SHARE_CHANNEL_NAME = "in.kalasetu/share";
    private static final int CAMERA_REQUEST = 201;
    private static final int GALLERY_REQUEST = 202;
    private static final int CAMERA_PERMISSION_REQUEST = 301;
    private static final int AUDIO_PERMISSION_REQUEST = 302;

    private MethodChannel.Result pendingResult;
    private String pendingPermissionAction;
    private MediaRecorder recorder;
    private File recordingFile;
    private File cameraOutputFile;

    @Override
    public void configureFlutterEngine(@NonNull FlutterEngine flutterEngine) {
        super.configureFlutterEngine(flutterEngine);
        new MethodChannel(
                flutterEngine.getDartExecutor().getBinaryMessenger(),
                CHANNEL_NAME
        ).setMethodCallHandler((call, result) -> {
            switch (call.method) {
                case "capturePhoto":
                    capturePhoto(result);
                    break;
                case "pickPhoto":
                    pickPhoto(result);
                    break;
                case "startVoiceRecording":
                    startVoiceRecording(result);
                    break;
                case "stopVoiceRecording":
                    stopVoiceRecording(result);
                    break;
                case "cancelVoiceRecording":
                    cancelVoiceRecording(result);
                    break;
                default:
                    result.notImplemented();
            }
        });
        new MethodChannel(
                flutterEngine.getDartExecutor().getBinaryMessenger(),
                SHARE_CHANNEL_NAME
        ).setMethodCallHandler((call, result) -> {
            if (!"shareText".equals(call.method)) {
                result.notImplemented();
                return;
            }
            String text = call.argument("text");
            if (text == null || text.trim().isEmpty()) {
                result.error("VALIDATION_ERROR", "Share text is required.", null);
                return;
            }
            Intent sendIntent = new Intent(Intent.ACTION_SEND);
            sendIntent.setType("text/plain");
            sendIntent.putExtra(Intent.EXTRA_TEXT, text);
            startActivity(Intent.createChooser(sendIntent, "Share catalogue"));
            result.success(null);
        });
    }

    private void capturePhoto(MethodChannel.Result result) {
        if (!hasPermission(Manifest.permission.CAMERA)) {
            requestPermission(
                    Manifest.permission.CAMERA,
                    CAMERA_PERMISSION_REQUEST,
                    "camera",
                    result
            );
            return;
        }

        File file = new File(
                getCacheDir(),
                "kalasetu_photo_" + System.currentTimeMillis() + ".jpg"
        );
        Uri outputUri = FileProvider.getUriForFile(
                this,
                getPackageName() + ".fileprovider",
                file
        );
        Intent intent = new Intent(MediaStore.ACTION_IMAGE_CAPTURE);
        intent.putExtra(MediaStore.EXTRA_OUTPUT, outputUri);
        intent.addFlags(
                Intent.FLAG_GRANT_WRITE_URI_PERMISSION | Intent.FLAG_GRANT_READ_URI_PERMISSION
        );
        if (intent.resolveActivity(getPackageManager()) == null) {
            result.error("CAMERA_UNAVAILABLE", "Camera is not available.", null);
            return;
        }
        pendingResult = result;
        cameraOutputFile = file;
        startActivityForResult(intent, CAMERA_REQUEST);
    }

    private void pickPhoto(MethodChannel.Result result) {
        pendingResult = result;
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("image/*");
        startActivityForResult(intent, GALLERY_REQUEST);
    }

    private void startVoiceRecording(MethodChannel.Result result) {
        if (!hasPermission(Manifest.permission.RECORD_AUDIO)) {
            requestPermission(
                    Manifest.permission.RECORD_AUDIO,
                    AUDIO_PERMISSION_REQUEST,
                    "audio",
                    result
            );
            return;
        }
        beginRecording(result);
    }

    @SuppressWarnings("deprecation")
    private void beginRecording(MethodChannel.Result result) {
        if (recorder != null) {
            result.error("INVALID_STATE", "A recording is already active.", null);
            return;
        }
        File file = new File(
                getCacheDir(),
                "kalasetu_voice_" + System.currentTimeMillis() + ".m4a"
        );
        MediaRecorder mediaRecorder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.S
                ? new MediaRecorder(this)
                : new MediaRecorder();
        try {
            mediaRecorder.setAudioSource(MediaRecorder.AudioSource.MIC);
            mediaRecorder.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4);
            mediaRecorder.setAudioEncoder(MediaRecorder.AudioEncoder.AAC);
            mediaRecorder.setAudioEncodingBitRate(128000);
            mediaRecorder.setAudioSamplingRate(44100);
            mediaRecorder.setMaxDuration(120000);
            mediaRecorder.setOutputFile(file.getAbsolutePath());
            mediaRecorder.prepare();
            mediaRecorder.start();
            recorder = mediaRecorder;
            recordingFile = file;
            result.success(null);
        } catch (Exception error) {
            mediaRecorder.release();
            file.delete();
            result.error(
                    "RECORDING_FAILED",
                    error.getMessage() == null ? "Recording could not start." : error.getMessage(),
                    null
            );
        }
    }

    private void stopVoiceRecording(MethodChannel.Result result) {
        if (recorder == null || recordingFile == null) {
            result.error("INVALID_STATE", "No recording is active.", null);
            return;
        }
        MediaRecorder activeRecorder = recorder;
        File file = recordingFile;
        try {
            activeRecorder.stop();
            activeRecorder.release();
            recorder = null;
            recordingFile = null;
            result.success(file.getAbsolutePath());
        } catch (RuntimeException error) {
            activeRecorder.release();
            recorder = null;
            recordingFile = null;
            file.delete();
            result.error(
                    "RECORDING_FAILED",
                    "Recording was too short or could not be saved.",
                    null
            );
        }
    }

    private void cancelVoiceRecording(MethodChannel.Result result) {
        releaseRecorder(true);
        result.success(null);
    }

    private boolean hasPermission(String permission) {
        return ContextCompat.checkSelfPermission(this, permission)
                == PackageManager.PERMISSION_GRANTED;
    }

    private void requestPermission(
            String permission,
            int requestCode,
            String action,
            MethodChannel.Result result
    ) {
        pendingResult = result;
        pendingPermissionAction = action;
        ActivityCompat.requestPermissions(this, new String[]{permission}, requestCode);
    }

    @Override
    public void onRequestPermissionsResult(
            int requestCode,
            @NonNull String[] permissions,
            @NonNull int[] grantResults
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        MethodChannel.Result result = pendingResult;
        if (result == null) {
            return;
        }
        boolean granted = grantResults.length > 0
                && grantResults[0] == PackageManager.PERMISSION_GRANTED;
        String action = pendingPermissionAction;
        pendingResult = null;
        pendingPermissionAction = null;
        if (!granted) {
            result.error("PERMISSION_DENIED", "Required permission was not granted.", null);
            return;
        }
        if ("camera".equals(action)) {
            capturePhoto(result);
        } else if ("audio".equals(action)) {
            beginRecording(result);
        }
    }

    @Override
    @SuppressWarnings("deprecation")
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != CAMERA_REQUEST && requestCode != GALLERY_REQUEST) {
            return;
        }
        MethodChannel.Result result = pendingResult;
        pendingResult = null;
        if (result == null) {
            return;
        }
        if (resultCode != Activity.RESULT_OK) {
            if (requestCode == CAMERA_REQUEST && cameraOutputFile != null) {
                cameraOutputFile.delete();
                cameraOutputFile = null;
            }
            result.success(null);
            return;
        }
        try {
            if (requestCode == CAMERA_REQUEST) {
                returnCameraPhoto(result);
            } else {
                copyGalleryImage(data == null ? null : data.getData(), result);
            }
        } catch (Exception error) {
            result.error(
                    "MEDIA_READ_FAILED",
                    error.getMessage() == null ? "Media could not be read." : error.getMessage(),
                    null
            );
        }
    }

    private void returnCameraPhoto(MethodChannel.Result result) {
        File file = cameraOutputFile;
        cameraOutputFile = null;
        if (file == null || !file.exists() || file.length() == 0) {
            if (file != null) {
                file.delete();
            }
            result.error("CAMERA_FAILED", "Camera did not return a photo.", null);
            return;
        }
        result.success(file.getAbsolutePath());
    }

    private void copyGalleryImage(Uri uri, MethodChannel.Result result) throws Exception {
        if (uri == null) {
            result.error("MEDIA_READ_FAILED", "No photo was selected.", null);
            return;
        }
        String mimeType = getContentResolver().getType(uri);
        if (mimeType == null) {
            mimeType = "image/jpeg";
        }
        String extension = MimeTypeMap.getSingleton().getExtensionFromMimeType(mimeType);
        if (extension == null) {
            extension = "jpg";
        }
        File file = new File(
                getCacheDir(),
                "kalasetu_gallery_" + System.currentTimeMillis() + "." + extension
        );
        try (
                InputStream input = getContentResolver().openInputStream(uri);
                FileOutputStream output = new FileOutputStream(file)
        ) {
            if (input == null) {
                throw new IllegalStateException("Selected photo could not be opened.");
            }
            byte[] buffer = new byte[8192];
            int count;
            while ((count = input.read(buffer)) != -1) {
                output.write(buffer, 0, count);
            }
        }
        result.success(file.getAbsolutePath());
    }

    private void releaseRecorder(boolean deleteFile) {
        if (recorder != null) {
            try {
                recorder.stop();
            } catch (RuntimeException ignored) {
                // A cancelled very short recording may not contain valid audio frames.
            }
            recorder.release();
            recorder = null;
        }
        if (deleteFile && recordingFile != null) {
            recordingFile.delete();
        }
        recordingFile = null;
    }

    @Override
    protected void onDestroy() {
        releaseRecorder(true);
        super.onDestroy();
    }
}
