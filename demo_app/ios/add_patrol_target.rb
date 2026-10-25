# Does the Xcode half of Patrol's iOS setup without clicking through Xcode:
# a RunnerUITests target set up like packages/patrol/example in the Patrol repo.
# Run once from demo_app/ios: ruby add_patrol_target.rb
require 'xcodeproj'

project = Xcodeproj::Project.open('Runner.xcodeproj')
abort 'RunnerUITests already exists' if project.targets.any? { |t| t.name == 'RunnerUITests' }
runner = project.targets.find { |t| t.name == 'Runner' }

uitests = project.new_target(:ui_test_bundle, 'RunnerUITests', :ios, '13.0', nil, :objc)
uitests.add_dependency(runner)

group = project.main_group.new_group('RunnerUITests', 'RunnerUITests')
uitests.add_file_references([group.new_reference('RunnerUITests.m')])

# Same configuration set as Runner, each on the Flutter xcconfig Runner uses,
# so FLUTTER_ROOT and the Pods settings reach the test bundle.
uitests.build_configuration_list.build_configurations.clear
runner.build_configurations.each do |rc|
  c = project.new(Xcodeproj::Project::Object::XCBuildConfiguration)
  c.name = rc.name
  c.base_configuration_reference = rc.base_configuration_reference
  c.build_settings = {
    'ALWAYS_EMBED_SWIFT_STANDARD_LIBRARIES' => 'YES',
    'CODE_SIGN_STYLE' => 'Automatic',
    'GENERATE_INFOPLIST_FILE' => 'YES',
    'IPHONEOS_DEPLOYMENT_TARGET' => rc.build_settings['IPHONEOS_DEPLOYMENT_TARGET'] ||
                                    project.build_configurations.first.build_settings['IPHONEOS_DEPLOYMENT_TARGET'] || '13.0',
    'PRODUCT_BUNDLE_IDENTIFIER' => 'dev.yii.boxtide.RunnerUITests',
    'PRODUCT_NAME' => '$(TARGET_NAME)',
    'SDKROOT' => 'iphoneos',
    'TARGETED_DEVICE_FAMILY' => '1,2',
    'TEST_TARGET_NAME' => 'Runner',
    'ENABLE_USER_SCRIPT_SANDBOXING' => 'NO',
  }
  uitests.build_configuration_list.build_configurations << c
end

# xcode_backend build before Sources, embed_and_thin last, as in Patrol's example.
build = uitests.new_shell_script_build_phase('xcode_backend build')
build.shell_script = "/bin/sh \"$FLUTTER_ROOT/packages/flutter_tools/bin/xcode_backend.sh\" build\n"
build.always_out_of_date = '1'
uitests.build_phases.delete(build)
uitests.build_phases.unshift(build)

embed = uitests.new_shell_script_build_phase('xcode_backend embed_and_thin')
embed.shell_script = "/bin/sh \"$FLUTTER_ROOT/packages/flutter_tools/bin/xcode_backend.sh\" embed_and_thin\n"
embed.input_paths = ['${TARGET_BUILD_DIR}/${INFOPLIST_PATH}']
embed.always_out_of_date = '1'

project.save

# Parallel execution breaks Patrol, so the testable is added with it off.
scheme_path = Xcodeproj::XCScheme.shared_data_dir('Runner.xcodeproj') + 'Runner.xcscheme'
scheme = Xcodeproj::XCScheme.new(scheme_path)
testable = Xcodeproj::XCScheme::TestAction::TestableReference.new(uitests)
testable.xml_element.attributes['parallelizable'] = 'NO'
scheme.test_action.add_testable(testable)
scheme.save!

puts "RunnerUITests added: #{uitests.build_phases.map(&:display_name).join(' | ')}"
