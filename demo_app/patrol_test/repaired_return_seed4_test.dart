import 'package:boxtide/app.dart';
import 'package:boxtide/data.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:patrol/patrol.dart';

// return-flow after `runner/repair.py` ran Jev on the seed-4 build and proposed
// new keys (results/repair-seed4.json). Generated, reviewed, kept to show the
// red test going green; it only runs against that build.

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
  patrolTest('return-flow repaired for seed 4', skip: _chaosSeed != 4, ($) async {
    await _signIn($);
    await $(#nav_orders_v14).tap();
    // The repair's extra: Jev scrolled here. The first Scrollable on this screen
    // is the row of filter chips, so name the order list instead.
    await $(#order_5207).scrollTo(view: find.byType(Scrollable).last).tap();
    await $(#start_return_button_v14).tap();
    await $(#return_next_button_v14).tap();
    await $(#return_next_button_v14).tap();
    await $(#return_confirm).tap();
    await $(#return_next_button_v14).tap();
    expect(Store.instance.orderById('5207').status, OrderStatus.returning);
  });
}
