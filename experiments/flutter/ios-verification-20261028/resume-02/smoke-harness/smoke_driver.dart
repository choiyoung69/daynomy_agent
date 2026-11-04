import 'dart:convert';
import 'dart:io';

import 'package:integration_test/integration_test_driver.dart';

Future<void> main() async {
  final output = Platform.environment['DAYNOMY_SMOKE_OUTPUT'];
  if (output == null || output.isEmpty) {
    throw StateError('DAYNOMY_SMOKE_OUTPUT must name the new verification output');
  }
  final folder = Directory(output);
  await folder.create(recursive: true);
  await integrationDriver(
    timeout: const Duration(minutes: 8),
    writeResponseOnFailure: true,
    responseDataCallback: (data) async {
      final screenshots = data?['screenshots'] as List<dynamic>? ?? [];
      final names = <String>[];
      for (final raw in screenshots) {
        final entry = raw as Map<String, dynamic>;
        final name = entry['screenshotName'] as String;
        if (!RegExp(r'^[a-z0-9-]+$').hasMatch(name)) {
          throw StateError('Unexpected screenshot name');
        }
        final bytes = (entry['bytes'] as List<dynamic>).cast<int>();
        await File('${folder.path}/$name.png').writeAsBytes(bytes);
        names.add('$name.png');
      }
      // No HTTP inputs, tokens, cookies, or raw screenshot bytes in JSON/logs.
      await File('${folder.path}/checkpoints.json').writeAsString(
        const JsonEncoder.withIndent('  ').convert({
          'checkpoints': data?['checkpoints'] ?? <String>[],
          'screenshots': names,
          'scope': 'production main and transport in an instrumented iOS test app',
        }),
      );
    },
  );
}
