// FILE: api_extra.dart - NEW (v6) calls for history, dashboard and fine-tuning. api.dart is unchanged and reused (apiBase, Json, Answer).
// Every function returns a Json map and never throws. On failure the map is {'error': 'message'} so the page can show it.
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'api.dart';

// ===== SECTION 1: small helpers =====
Json _decode(http.Response r) {
  try {
    final j = jsonDecode(utf8.decode(r.bodyBytes));
    if (r.statusCode != 200) return {'error': (j is Map && j['detail'] != null) ? '${j['detail']}' : 'HTTP ${r.statusCode}'};
    return j as Json;
  } catch (_) {
    return {'error': 'HTTP ${r.statusCode}'};
  }
}

Future<Json> _call(Future<http.Response> Function() f) async {
  try {
    return _decode(await f());
  } catch (e) {
    return {'error': 'Cannot reach the backend at $apiBase ($e).'};
  }
}

Future<Json> _get(String path) => _call(() => http.get(Uri.parse('$apiBase$path')).timeout(const Duration(seconds: 20)));
Future<Json> _post(String path, Json body, int seconds) => _call(() => http
    .post(Uri.parse('$apiBase$path'), headers: {'Content-Type': 'application/json'}, body: jsonEncode(body))
    .timeout(Duration(seconds: seconds)));

// ===== SECTION 2: chat with a chosen conversation id (used by Chat and by "Resume chat") =====
Future<Answer> askIn(String question, String sid) async {
  final j = await _post('/ask', {'question': question, 'session_id': sid}, 90);
  if (j['error'] != null) return Answer(status: 'error', message: '${j['error']}');
  return Answer.fromJson(j);
}

// ===== SECTION 3: history =====
Future<Json> fetchHistory() => _get('/history');
Future<Json> fetchSession(String sid) => _get('/history/${Uri.encodeComponent(sid)}');
Future<Json> deleteSession(String sid) => _call(() => http.delete(Uri.parse('$apiBase/history/${Uri.encodeComponent(sid)}')).timeout(const Duration(seconds: 15)));

// ===== SECTION 4: dashboard =====
Future<Json> fetchDashboard() => _get('/dashboard');

// ===== SECTION 5: fine-tuning page =====
Future<Json> tuningStatus() => _get('/tuning/status');
Future<Json> tuningGenerate(int n) => _post('/tuning/generate', {'n': n}, 120);
Future<Json> tuningEvaluate(String mode, int limit) => _post('/tuning/evaluate', {'mode': mode, 'limit': limit}, 300);
