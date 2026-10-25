import 'package:boxtide/app.dart';
import 'package:boxtide/data.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:patrol/patrol.dart';

// The four flows `runner/agent.py` scripts, as Patrol tests: the same keys in
// the same order. Each ends by asking the store, not the screen, whether the
// task happened, which a test running inside the app can do directly.

/// Baked in with --dart-define, the same churn the e2e chaos build carries.
const _chaosSeed = int.fromEnvironment('CHAOS_SEED');

Future<void> _signIn(PatrolIntegrationTester $) async {
  Store.instance
    ..reset()
    ..setChaos(_chaosSeed);
  await $.pumpWidgetAndSettle(const BoxtideApp());
  await $(#email_field).enterText('demo@example.com');
  await $(#password_field).enterText('hunter2');
  await $(#signin_button).tap();
}

void main() {
  patrolTest('return-flow', ($) async {
    await _signIn($);
    await $(#nav_orders).tap();
    await $(#order_5207).tap();
    await $(#start_return_button).tap();
    await $(#return_next_button).tap();
    await $(#return_next_button).tap();
    await $(#return_confirm).tap();
    await $(#return_next_button).tap();
    expect(Store.instance.orderById('5207').status, OrderStatus.returning);
  });

  patrolTest('cart-flow', ($) async {
    await _signIn($);
    await $(#nav_shop).tap();
    await $(const Key('product_p-speaker')).scrollTo().tap();
    await $(#add_to_cart_button).tap();
    await $(#view_cart_button).tap();
    expect(Store.instance.cart['p-speaker'] ?? 0, greaterThanOrEqualTo(1));
  });

  patrolTest('support-flow', ($) async {
    await _signIn($);
    await $(#nav_support).tap();
    await $(#contact_us_button).scrollTo().tap();
    await $(#contact_order_field).enterText('5213');
    await $(#contact_message_field).enterText('My parcel has not moved in four days.');
    await $(#contact_send_button).tap();
    expect(Store.instance.tickets.any((t) => t['order']!.contains('5213')), isTrue);
  });

  patrolTest('address-flow', ($) async {
    await _signIn($);
    await $(#nav_account).tap();
    await $(#profile_addresses).tap();
    await $(#add_address_button).scrollTo().tap();
    await $(#address_label_field).enterText('Office');
    await $(#address_lines_field).enterText('9F, 100 Taiyuan Rd');
    await $(#address_save_button).tap();
    expect(
      Store.instance.addresses.any((a) => a.label.trim().toLowerCase() == 'office'),
      isTrue,
    );
  });
}
