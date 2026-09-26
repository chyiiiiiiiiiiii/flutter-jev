import 'package:flutter/material.dart';

import 'data.dart';
import 'screens/auth.dart';
import 'theme.dart';

class BoxtideApp extends StatelessWidget {
  const BoxtideApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Boxtide',
      debugShowCheckedModeBanner: false,
      theme: Tk.theme(),
      // Rebuilt from scratch when the churn changes, because a screen that is
      // already on screen will not pick up a rename otherwise: only the parts
      // that listen to the store would, and most screens do not.
      home: ListenableBuilder(
        listenable: Store.instance,
        builder: (context, _) =>
            SignInScreen(key: ValueKey(Store.instance.chaosSeed)),
      ),
    );
  }
}
