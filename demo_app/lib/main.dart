import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:marionette_flutter/marionette_flutter.dart';

import 'app.dart';
import 'data.dart';

void main() {
  // Marionette must be the only binding in the process, and only outside release.
  if (!kReleaseMode) {
    MarionetteBinding.ensureInitialized();
    _registerChaos();
    _registerState();
  } else {
    WidgetsFlutterBinding.ensureInitialized();
  }
  runApp(const BoxtideApp());
}

/// Lets a test runner churn the app the way a development team does.
///
/// Renaming a key, reordering a list or adding a confirmation step is a normal
/// week for a real app, and it is exactly what breaks a hand-written test. The
/// seed makes a particular churn reproducible, so the same drift can be
/// replayed against a script and against an agent.
void _registerChaos() {
  registerMarionetteExtension(
    name: 'boxtide.setChaos',
    description:
        'Rename widget keys, swap button labels, reorder the order '
        'list and sometimes add a confirmation step. 0 turns it off.',
    inputSchema: ExtensionInputSchema(
      properties: {
        'seed': ExtensionParam.integer(
          description:
              'Any non-zero integer picks a reproducible churn; '
              '0 restores the app a test was written against.',
          defaultValue: 0,
        ),
      },
      required: ['seed'],
    ),
    callback: (params) async {
      final seed = int.tryParse(params['seed'] ?? '0');
      if (seed == null) {
        return MarionetteExtensionResult.invalidParams(
          'seed must be an integer',
        );
      }
      Store.instance.setChaos(seed);
      return MarionetteExtensionResult.success({
        'seed': '$seed',
        'keySuffix': Store.instance.keySuffix,
        'extraConfirmStep': '${Store.instance.extraConfirmStep}',
      });
    },
  );
}

/// What the app actually holds, for checking a run against the world instead
/// of against the agent's own claim that it finished.
void _registerState() {
  registerMarionetteExtension(
    name: 'boxtide.state',
    description: 'Orders, cart, addresses and support tickets as JSON.',
    inputSchema: ExtensionInputSchema(properties: {}, required: []),
    callback: (params) async {
      final s = Store.instance;
      return MarionetteExtensionResult.success({
        'json': jsonEncode({
          'signedIn': s.signedIn,
          'orders': {for (final o in s.orders) o.id: o.status.name},
          'cart': s.cart,
          'addresses': [
            for (final a in s.addresses) {'label': a.label, 'lines': a.lines},
          ],
          'tickets': s.tickets,
        }),
      });
    },
  );
}
