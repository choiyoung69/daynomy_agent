import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import 'daynomy.dart';
import 'src/transport.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  const configured = String.fromEnvironment('API_BASE_URL');
  final base = Uri.parse(
    configured.isNotEmpty
        ? configured
        : kIsWeb
        ? Uri.base.origin
        : 'https://api.daynomy.invalid',
  );
  try {
    final transport = PlatformTransport(base);
    final client = ApiClient(transport: transport)
      ..onRequestsInvalidated = transport.invalidateRequests;
    runApp(
      DaynomyApp(
        repository: AppRepository(client),
        onLogin: () => transport.login(client),
        onOpenLink: transport.openLink,
        onSessionCleared: transport.clearSession,
      ),
    );
  } catch (_) {
    runApp(
      const MaterialApp(
        home: Scaffold(
          body: SafeArea(
            child: Padding(
              padding: EdgeInsets.all(24),
              child: Text(
                'API 주소를 확인해주세요. HTTPS origin을 설정하거나 명시적인 로컬 개발 주소를 사용하세요.',
              ),
            ),
          ),
        ),
      ),
    );
  }
}
