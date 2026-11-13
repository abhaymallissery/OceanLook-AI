import 'package:flutter_test/flutter_test.dart';
import 'package:floatchat/main.dart';

void main() {
  testWidgets('App smoke test', (WidgetTester tester) async {
    await tester.pumpWidget(const FloatChatApp());
    expect(find.byType(FloatChatApp), findsOneWidget);
  });
}
