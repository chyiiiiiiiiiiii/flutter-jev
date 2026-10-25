import 'package:flutter/material.dart';

// Which way of tagging a TextField for black-box tools keeps it a text field
// in the iOS accessibility tree? One field per variant, same screen.
void main() => runApp(const MaterialApp(home: Probe()));

class Probe extends StatelessWidget {
  const Probe({super.key});

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Probe')),
        body: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            const TextField(decoration: InputDecoration(labelText: 'A plain')),
            Semantics(
              identifier: 'b_identifier',
              child: const TextField(decoration: InputDecoration(labelText: 'B identifier')),
            ),
            Semantics(
              identifier: 'c_container',
              container: true,
              child: const TextField(decoration: InputDecoration(labelText: 'C identifier container')),
            ),
            Semantics(
              identifier: 'd_textfield',
              textField: true,
              child: const TextField(decoration: InputDecoration(labelText: 'D identifier textField')),
            ),
            Semantics(
              identifier: 'e_obscured',
              container: true,
              child: const TextField(obscureText: true, decoration: InputDecoration(labelText: 'E password container')),
            ),
            const TextField(obscureText: true, decoration: InputDecoration(labelText: 'F password plain')),
          ],
        ),
      );
}
