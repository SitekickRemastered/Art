using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEditor.Animations;
using UnityEngine;

/// <summary>
/// Batch verification of the chip effect animations: every generated prefab must
/// carry an Animator bound to a controller whose default state plays the chip
/// clip, every curve binding must resolve inside the prefab, and the parts must
/// actually change pose over the clip.  Writes Logs/chip-animation-validation.txt.
/// </summary>
public static class ChipAnimValidate
{
	const string CHIPS = "Assets/Chips";
	const float MOTION_EPS = 1e-4f;

	public static void Run()
	{
		var prefabs = AssetDatabase.FindAssets( "t:Prefab", new[] { CHIPS } )
			.Select( AssetDatabase.GUIDToAssetPath )
			.Where( p => p.EndsWith( "_Effect.prefab" ) )
			.OrderBy( p => p )
			.ToArray();

		int withAnimator = 0, missingController = 0, badState = 0, noCurves = 0;
		int animatedRoots = 0, movedRoots = 0, staticRoots = 0;
		int badBindings = 0, badDuration = 0, notLooping = 0, spriteSwaps = 0;
		var problems = new List<string>();
		var unmoved = new List<string>();
		var swapped = new List<string>();

		foreach ( var path in prefabs )
		{
			var root = AssetDatabase.LoadAssetAtPath<GameObject>( path );
			if ( root == null ) { problems.Add( path + ": failed to load" ); continue; }

			var animator = root.GetComponent<Animator>();
			if ( animator == null ) continue;
			withAnimator++;

			var ctrl = animator.runtimeAnimatorController as AnimatorController;
			if ( ctrl == null ) { missingController++; problems.Add( path + ": Animator has no controller" ); continue; }

			int curveCount = 0;
			var clip = ctrl.layers[0].stateMachine.defaultState?.motion as AnimationClip;
			if ( clip == null )
			{
				badState++;
				problems.Add( path + ": default state has no clip" );
				continue;
			}

			// a sprite swap is an object-reference curve: it is not in GetCurveBindings
			var bindings = AnimationUtility.GetCurveBindings( clip )
				.Concat( AnimationUtility.GetObjectReferenceCurveBindings( clip ) ).ToArray();
			curveCount = bindings.Length;
			if ( curveCount == 0 ) { noCurves++; problems.Add( path + ": clip has no curves" ); continue; }

			// every binding path must exist under the prefab root
			var transforms = root.GetComponentsInChildren<Transform>( true ).Select( t => t.name ).ToHashSet();
			foreach ( var b in bindings )
			{
				if ( string.IsNullOrEmpty( b.path ) ) continue;
				var leaf = b.path.Split( '/' ).Last();
				if ( !transforms.Contains( leaf ) )
				{
					badBindings++;
					problems.Add( $"{path}: binding path '{b.path}' not found" );
					break;
				}
			}

			if ( clip.wrapMode != WrapMode.Loop ) { notLooping++; problems.Add( path + ": clip is not looping" ); }

			// motion check: sample the clip at two times
			var go = (GameObject) PrefabUtility.InstantiatePrefab( root );
			var renderers = go.GetComponentsInChildren<SpriteRenderer>( true ).OrderBy( r => r.name ).ToArray();
			clip.SampleAnimation( go, 0f );
			var startSprites = renderers.Select( r => r.sprite ).ToArray();
			bool spriteSwap = false;
			float spriteDuration = Mathf.Max( clip.length, 0.001f );
			for ( int s = 1; s <= 4; s++ )
			{
				clip.SampleAnimation( go, spriteDuration * ( s / 5f ) );
				for ( int r = 0; r < renderers.Length; r++ )
					if ( renderers[r].sprite != startSprites[r] ) spriteSwap = true;
			}
			if ( spriteSwap ) { spriteSwaps++; swapped.Add( Path.GetFileNameWithoutExtension( path ) ); }

			var parts = go.GetComponentsInChildren<Transform>( true )
				.Where( t => t != go.transform && t.name.StartsWith( "chip_" ) && t.name.Contains( "_part_" ) )
				.ToArray();

			if ( parts.Length == 0 )
			{
				Object.DestroyImmediate( go );
				if ( spriteSwap ) movedRoots++;
				continue;
			}

			animatedRoots++;

			clip.SampleAnimation( go, 0f );
			var before = parts.Select( t => ( t.localPosition, t.localRotation, t.localScale ) ).ToArray();
			float duration = Mathf.Max( clip.length, 0.001f );

			float best = 0f;
			for ( int i = 1; i <= 4; i++ )
			{
				clip.SampleAnimation( go, duration * ( i / 5f ) );
				for ( int p = 0; p < parts.Length; p++ )
				{
					best = Mathf.Max( best, ( parts[p].localPosition - before[p].localPosition ).magnitude );
					best = Mathf.Max( best, Quaternion.Angle( parts[p].localRotation, before[p].localRotation ) / 90f );
					best = Mathf.Max( best, ( parts[p].localScale - before[p].localScale ).magnitude );
				}
			}
			Object.DestroyImmediate( go );

			if ( best > MOTION_EPS || spriteSwap ) movedRoots++;
			else { staticRoots++; unmoved.Add( path ); }

			var expected = clip.length;
			if ( Mathf.Abs( expected - ( clip.length ) ) > 1e-3f ) badDuration++;
		}

		var report = new StringBuilder();
		report.AppendLine( $"prefabs: {prefabs.Length}  with Animator: {withAnimator}" );
		report.AppendLine( $"  missing controller: {missingController}  default state without clip: {badState}" );
		report.AppendLine( $"  clips without curves: {noCurves}  unresolved binding paths: {badBindings}  not looping: {notLooping}" );
					report.AppendLine( $"  animatable roots: {animatedRoots}  parts move: {movedRoots}  static pose only: {staticRoots}" );
			report.AppendLine( $"  sprite-swapping chips: {spriteSwaps}" +
				( swapped.Count > 0 ? " (" + string.Join( ", ", swapped ) + ")" : "" ) );
		report.AppendLine( $"problems: {problems.Count}" );
		foreach ( var p in problems.Take( 30 ) ) report.AppendLine( "  " + p );
		if ( unmoved.Count > 0 )
			report.AppendLine( $"single-pose chips ({unmoved.Count}): " + string.Join( ", ",
				unmoved.Select( p => Path.GetFileNameWithoutExtension( p ) ).Take( 20 ) ) );
		report.AppendLine( problems.Count == 0 ? "RESULT: OK" : "RESULT: PROBLEMS" );

		Directory.CreateDirectory( "Logs" );
		File.WriteAllText( "Logs/chip-animation-validation.txt", report.ToString() );
		Debug.Log( "[ChipAnimValidate]\n" + report );
	}
}
