import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:boxtide/app.dart';
import 'package:boxtide/data.dart';

/// The hand-written baseline the agent-driven runs are measured against.
/// Every step here names the widget it drives, which is exactly the coupling
/// the agent approach is trying to remove.
void main() {
  setUp(Store.instance.reset);

  // The app is laid out for a phone; the default 800x600 test surface is not
  // a shape any user sees, and testing against it only invents overflows.
  setUp(() {
    final view = TestWidgetsFlutterBinding.instance.platformDispatcher.views.first;
    view.physicalSize = const Size(1179, 2556);
    view.devicePixelRatio = 3.0;
  });

  tearDown(() {
    final view = TestWidgetsFlutterBinding.instance.platformDispatcher.views.first;
    view.resetPhysicalSize();
    view.resetDevicePixelRatio();
  });

  Future<void> signIn(WidgetTester tester) async {
    await tester.pumpWidget(const BoxtideApp());
    await tester.enterText(
        find.byKey(const Key('email_field')), 'demo@example.com');
    await tester.enterText(find.byKey(const Key('password_field')), 'hunter2');
    await tester.tap(find.byKey(const Key('signin_button')));
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));
    await tester.pumpAndSettle();
  }

  testWidgets('sign in, open a delivered order, and submit a return',
      (tester) async {
    await signIn(tester);

    await tester.tap(find.byKey(const Key('nav_orders')));
    await tester.pump(const Duration(seconds: 1));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('order_5207')));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('start_return_button')));
    await tester.pumpAndSettle();

    // Step 1 pre-selects the only line item, so Continue is already enabled.
    await tester.tap(find.byKey(const Key('return_next_button')));
    await tester.pumpAndSettle();

    // Step 2 is all optional fields.
    await tester.tap(find.byKey(const Key('return_next_button')));
    await tester.pumpAndSettle();

    // Step 3 gates submission on the confirmation checkbox.
    await tester.tap(find.byKey(const Key('return_confirm')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('return_next_button')));
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('return_done_headline')), findsOneWidget);
    expect(Store.instance.orderById('5207').status, OrderStatus.returning);
  });

  testWidgets('a return is blocked while the order is still in transit',
      (tester) async {
    await signIn(tester);

    await tester.tap(find.byKey(const Key('nav_orders')));
    await tester.pump(const Duration(seconds: 1));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('order_5213')));
    await tester.pumpAndSettle();

    final button = tester.widget<FilledButton>(
      find.byKey(const Key('start_return_button')),
    );
    expect(button.onPressed, isNull);
  });

  testWidgets('submission stays blocked until the confirmation is checked',
      (tester) async {
    await signIn(tester);

    await tester.tap(find.byKey(const Key('nav_orders')));
    await tester.pump(const Duration(seconds: 1));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('order_5198')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('start_return_button')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('return_next_button')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('return_next_button')));
    await tester.pumpAndSettle();

    final blocked = tester.widget<FilledButton>(
      find.byKey(const Key('return_next_button')),
    );
    expect(blocked.onPressed, isNull);
  });

  testWidgets('the orders list surfaces an error state and recovers',
      (tester) async {
    Store.instance.simulateOrdersError = true;
    await signIn(tester);

    await tester.tap(find.byKey(const Key('nav_orders')));
    await tester.pump(const Duration(seconds: 1));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('orders_error')), findsOneWidget);

    Store.instance.simulateOrdersError = false;
    await tester.tap(find.byKey(const Key('orders_retry_button')));
    await tester.pump(const Duration(seconds: 1));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('orders_error')), findsNothing);
    expect(find.byKey(const Key('order_5207')), findsOneWidget);
  });

  _persistenceTests();

  testWidgets('searching the orders list narrows it and can go empty',
      (tester) async {
    await signIn(tester);

    await tester.tap(find.byKey(const Key('nav_orders')));
    await tester.pump(const Duration(seconds: 1));
    await tester.pumpAndSettle();

    await tester.enterText(find.byKey(const Key('orders_search')), 'pour-over');
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('order_5207')), findsOneWidget);
    expect(find.byKey(const Key('order_5213')), findsNothing);

    await tester.enterText(find.byKey(const Key('orders_search')), 'zzzz');
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('orders_empty')), findsOneWidget);
  });
}

Future<void> _signIn(WidgetTester tester) async {
  await tester.enterText(
      find.byKey(const Key('email_field')), 'demo@example.com');
  await tester.enterText(find.byKey(const Key('password_field')), 'hunter2');
  await tester.tap(find.byKey(const Key('signin_button')));
  await tester.pump();
  await tester.pump(const Duration(seconds: 1));
  await tester.pumpAndSettle();
}

/// These exist because the first version of the address and card sheets showed
/// a confirmation and persisted nothing. A test that only asserted the SnackBar
/// would have passed. Assert the store instead.
void _persistenceTests() {
  testWidgets('saving a new address actually adds it to the list',
      (tester) async {
    await tester.pumpWidget(const BoxtideApp());
    await _signIn(tester);

    await tester.tap(find.byKey(const Key('nav_account')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('profile_addresses')));
    await tester.pumpAndSettle();

    final before = Store.instance.addresses.length;
    await tester.tap(find.byKey(const Key('add_address_button')));
    await tester.pumpAndSettle();

    await tester.enterText(find.byKey(const Key('address_label_field')), 'Office');
    await tester.enterText(
        find.byKey(const Key('address_lines_field')), '9F, 100 Taiyuan Rd');
    await tester.tap(find.byKey(const Key('address_save_button')));
    await tester.pumpAndSettle();

    expect(Store.instance.addresses.length, before + 1);
    expect(find.byKey(const Key('address_addr_office')), findsOneWidget);
  });

  testWidgets('an address with no label is rejected rather than saved',
      (tester) async {
    await tester.pumpWidget(const BoxtideApp());
    await _signIn(tester);

    await tester.tap(find.byKey(const Key('nav_account')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('profile_addresses')));
    await tester.pumpAndSettle();

    final before = Store.instance.addresses.length;
    await tester.tap(find.byKey(const Key('add_address_button')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('address_save_button')));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('address_error')), findsOneWidget);
    expect(Store.instance.addresses.length, before);
  });

  testWidgets('saving a card adds it with the last four digits',
      (tester) async {
    await tester.pumpWidget(const BoxtideApp());
    await _signIn(tester);

    await tester.tap(find.byKey(const Key('nav_account')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('profile_payments')));
    await tester.pumpAndSettle();

    final before = Store.instance.payments.length;
    await tester.tap(find.byKey(const Key('add_payment_button')));
    await tester.pumpAndSettle();
    await tester.enterText(
        find.byKey(const Key('card_number_field')), '4242424242421234');
    await tester.enterText(find.byKey(const Key('card_expiry_field')), '11/30');
    await tester.tap(find.byKey(const Key('card_save_button')));
    await tester.pumpAndSettle();

    expect(Store.instance.payments.length, before + 1);
    expect(Store.instance.payments.last.label, contains('1234'));
  });
}
