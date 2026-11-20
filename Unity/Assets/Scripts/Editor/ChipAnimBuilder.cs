using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEditor.Animations;
using UnityEngine;

/// <summary>
/// Authors the looping AnimationClip and AnimatorController of every animated chip
/// from the plan produced by Tools/SwfToSvg/build_anim_plan.py, the same way
/// Chip_0099 was wired: clip in Animations/Chip_XXXX.anim, controller in
/// Animations/chip_XXXX.controller, one looping default state.
/// </summary>
public static class ChipAnimBuilder
{
	const string PLAN = "Tools/SwfToSvg/anim_plan.txt";
	const string CHIPS = "Assets/Chips";

	class Key
	{
		public float t, px, py, rz, sx, sy, a;
	}

	class Part
	{
		public string path;
		public readonly List<Key> keys = new List<Key>();
	}

	class Aux
	{
		public string name;
		public float duration;
		public readonly List<string> swapPaths = new List<string>();
		public readonly List<string[]> swapAssets = new List<string[]>();
		public readonly List<Vector3> moves = new List<Vector3>(); // t, y, alpha
	}

	class Chip
	{
		public int id, fps, frames;
		public readonly List<Part> parts = new List<Part>();
		public readonly List<Aux> aux = new List<Aux>();
	}

	static Chip[] ParsePlan( string file )
	{
		var chips = new List<Chip>();
		Chip cur = null;
		Part part = null;
		Aux aux = null;
		foreach ( var raw in File.ReadAllLines( file ) )
		{
			var line = raw.Trim();
			if ( line.Length == 0 ) continue;
			var f = line.Split( ' ' );
			switch ( f[0] )
			{
				case "AUX":
					aux = new Aux { name = f[1], duration = F( f[2] ) };
					cur.aux.Add( aux );
					part = null;
					break;
				case "SWAP":
					aux.swapPaths.Add( f[1] );
					aux.swapAssets.Add( f.Skip( 2 ).ToArray() );
					break;
				case "M":
					aux.moves.Add( new Vector3( F( f[1] ), F( f[2] ), F( f[3] ) ) );
					break;
				case "END":
					aux = null;
					break;
				case "CHIP":
					cur = new Chip
					{
						id = int.Parse( f[1] ), fps = int.Parse( f[2] ), frames = int.Parse( f[3] )
					};
					chips.Add( cur );
					part = null;
					break;
				case "PART":
					part = new Part { path = f[1] };
					cur.parts.Add( part );
					break;
				case "K":
					part.keys.Add( new Key
					{
						t = F( f[1] ), px = F( f[2] ), py = F( f[3] ), rz = F( f[4] ),
						sx = F( f[5] ), sy = F( f[6] ), a = F( f[7] )
					} );
					break;
			}
		}
		return chips.ToArray();
	}

	static float F( string s ) => float.Parse( s, CultureInfo.InvariantCulture );

	static AnimationCurve Curve( IEnumerable<KeyValuePair<float, float>> values )
	{
		var curve = new AnimationCurve();
		foreach ( var kv in values )
		{
			var k = new Keyframe( kv.Key, kv.Value );
			k.inTangent = float.PositiveInfinity;
			k.outTangent = float.PositiveInfinity;
			curve.AddKey( k );
		}
		return curve;
	}

	static string ChipDir( int id )
	{
		int lo = ( ( id - 1 ) / 100 ) * 100 + 1;
		string range = string.Format( "{0:0000}-{1:0000}", lo, lo + 99 );
		return Path.Combine( Path.Combine( Path.Combine( CHIPS, range ), string.Format( "Chip_{0:0000}", id ) ), "Animations" )
			.Replace( '\\', '/' );
	}

	static void EnsureFolder( string assetFolder )
	{
		if ( AssetDatabase.IsValidFolder( assetFolder ) ) return;
		var parent = Path.GetDirectoryName( assetFolder ).Replace( '\\', '/' );
		var name = Path.GetFileName( assetFolder );
		EnsureFolder( parent );
		AssetDatabase.CreateFolder( parent, name );
	}

	public static void Run()
	{
		var chips = ParsePlan( PLAN );
		int clips = 0, controllers = 0, skipped = 0, auxClips = 0, auxControllers = 0;
		var problems = new List<string>();

		foreach ( var chip in chips )
		{
			string folder = ChipDir( chip.id );
			string clipPath = $"{folder}/Chip_{chip.id:0000}.anim";
			string ctrlPath = $"{folder}/chip_{chip.id:0000}.controller";

			EnsureFolder( folder );

			if ( AssetDatabase.LoadAssetAtPath<AnimationClip>( clipPath ) != null )
				AssetDatabase.DeleteAsset( clipPath );
			if ( AssetDatabase.LoadAssetAtPath<AnimatorController>( ctrlPath ) != null )
				AssetDatabase.DeleteAsset( ctrlPath );

			var clip = new AnimationClip { name = $"Chip_{chip.id:0000}" };
			int curves = 0;

			foreach ( var part in chip.parts )
			{
				if ( part.keys.Count == 0 ) continue;

				AnimationUtility.SetEditorCurve( clip,
					EditorCurveBinding.FloatCurve( part.path, typeof( Transform ), "m_LocalPosition.x" ),
					Curve( part.keys.Select( k => new KeyValuePair<float, float>( k.t, k.px ) ) ) );
				AnimationUtility.SetEditorCurve( clip,
					EditorCurveBinding.FloatCurve( part.path, typeof( Transform ), "m_LocalPosition.y" ),
					Curve( part.keys.Select( k => new KeyValuePair<float, float>( k.t, k.py ) ) ) );
				AnimationUtility.SetEditorCurve( clip,
					EditorCurveBinding.FloatCurve( part.path, typeof( Transform ), "localEulerAnglesRaw.z" ),
					Curve( part.keys.Select( k => new KeyValuePair<float, float>( k.t, k.rz ) ) ) );
				AnimationUtility.SetEditorCurve( clip,
					EditorCurveBinding.FloatCurve( part.path, typeof( Transform ), "m_LocalScale.x" ),
					Curve( part.keys.Select( k => new KeyValuePair<float, float>( k.t, k.sx ) ) ) );
				AnimationUtility.SetEditorCurve( clip,
					EditorCurveBinding.FloatCurve( part.path, typeof( Transform ), "m_LocalScale.y" ),
					Curve( part.keys.Select( k => new KeyValuePair<float, float>( k.t, k.sy ) ) ) );
				curves += 5;

				bool varyingAlpha = part.keys.Any( k => Mathf.Abs( k.a - part.keys[0].a ) > 1e-4f ) || part.keys[0].a < 0.999f;
				if ( varyingAlpha )
				{
					AnimationUtility.SetEditorCurve( clip,
						EditorCurveBinding.FloatCurve( part.path + "/sprite", typeof( SpriteRenderer ), "m_Color.a" ),
						Curve( part.keys.Select( k => new KeyValuePair<float, float>( k.t, k.a ) ) ) );
					curves++;
				}
			}

			if ( curves == 0 && chip.aux.Count == 0 )
			{
				skipped++;
				continue;
			}

		// a background chip has no parts of its own, only clips
		if ( curves > 0 )
		{

			clip.frameRate = chip.fps;
			clip.wrapMode = WrapMode.Loop;
			var settings = AnimationUtility.GetAnimationClipSettings( clip );
			settings.loopTime = true;
			settings.stopTime = chip.frames / (float) chip.fps;
			AnimationUtility.SetAnimationClipSettings( clip, settings );

			AssetDatabase.CreateAsset( clip, clipPath );
			clips++;

			var ctrl = AnimatorController.CreateAnimatorControllerAtPath( ctrlPath );
			var sm = ctrl.layers[0].stateMachine;
			var state = sm.AddState( $"Chip_{chip.id:0000}" );
			state.motion = clip;
			state.writeDefaultValues = true;
			sm.defaultState = state;
			EditorUtility.SetDirty( ctrl );
			controllers++;
		}

			// clips that do not belong to the effect timeline: a backdrop/foreground
			// plays its own frames, a spawned particle crosses the stage
			foreach ( var a in chip.aux )
			{
				string auxClipPath = $"{folder}/Chip_{chip.id:0000}_{a.name}.anim";
				string auxCtrlPath = $"{folder}/chip_{chip.id:0000}_{a.name}.controller";
				if ( AssetDatabase.LoadAssetAtPath<AnimationClip>( auxClipPath ) != null )
					AssetDatabase.DeleteAsset( auxClipPath );
				if ( AssetDatabase.LoadAssetAtPath<AnimatorController>( auxCtrlPath ) != null )
					AssetDatabase.DeleteAsset( auxCtrlPath );

				var auxClip = new AnimationClip { name = $"{chip.id:0000}_{a.name}" };
				int auxCurves = 0;

				for ( int i = 0; i < a.swapPaths.Count; i++ )
				{
					var keys = new List<ObjectReferenceKeyframe>();
					foreach ( var assetPath in a.swapAssets[i] )
					{
						var sprite = AssetDatabase.LoadAllAssetsAtPath( assetPath ).OfType<Sprite>().FirstOrDefault();
						if ( sprite == null ) continue;
						keys.Add( new ObjectReferenceKeyframe
						{
							time = keys.Count / (float) chip.fps,
							value = sprite
						} );
					}
					if ( keys.Count == 0 ) continue;
					AnimationUtility.SetObjectReferenceCurve( auxClip,
						EditorCurveBinding.PPtrCurve( a.swapPaths[i], typeof( SpriteRenderer ), "m_Sprite" ),
						keys.ToArray() );
					auxCurves++;
				}

				if ( a.moves.Count > 0 )
				{
					AnimationUtility.SetEditorCurve( auxClip,
						EditorCurveBinding.FloatCurve( "", typeof( Transform ), "m_LocalPosition.y" ),
						Curve( a.moves.Select( m => new KeyValuePair<float, float>( m.x, m.y ) ) ) );
					AnimationUtility.SetEditorCurve( auxClip,
						EditorCurveBinding.FloatCurve( "sprite", typeof( SpriteRenderer ), "m_Color.a" ),
						Curve( a.moves.Select( m => new KeyValuePair<float, float>( m.x, m.z ) ) ) );
					auxCurves += 2;
				}

				if ( auxCurves == 0 ) continue;

				auxClip.frameRate = chip.fps;
				auxClip.wrapMode = WrapMode.Loop;
				var auxSettings = AnimationUtility.GetAnimationClipSettings( auxClip );
				auxSettings.loopTime = true;
				auxSettings.stopTime = a.duration > 0f ? a.duration : 1f;
				AnimationUtility.SetAnimationClipSettings( auxClip, auxSettings );
				AssetDatabase.CreateAsset( auxClip, auxClipPath );
				auxClips++;

				var auxCtrl = AnimatorController.CreateAnimatorControllerAtPath( auxCtrlPath );
				var auxSm = auxCtrl.layers[0].stateMachine;
				var auxState = auxSm.AddState( $"{chip.id:0000}_{a.name}" );
				auxState.motion = auxClip;
				auxState.writeDefaultValues = true;
				auxSm.defaultState = auxState;
				EditorUtility.SetDirty( auxCtrl );
				auxControllers++;
			}
		}

		AssetDatabase.SaveAssets();
		AssetDatabase.Refresh();

		// verify the assets bind back to the clip correctly
		int badBind = 0;
		foreach ( var chip in chips )
		{
			string folder = ChipDir( chip.id );
			if ( chip.parts.Count == 0 )
			{
				// a background chip has no parts, only its own clips
				foreach ( var a in chip.aux )
				{
					var ac = AssetDatabase.LoadAssetAtPath<AnimationClip>( $"{folder}/Chip_{chip.id:0000}_{a.name}.anim" );
					var ao = AssetDatabase.LoadAssetAtPath<AnimatorController>( $"{folder}/chip_{chip.id:0000}_{a.name}.controller" );
					if ( ac == null || ao == null )
					{
						badBind++;
						problems.Add( $"{chip.id} {a.name}: missing aux asset" );
					}
				}
				continue;
			}
			var clip = AssetDatabase.LoadAssetAtPath<AnimationClip>( $"{folder}/Chip_{chip.id:0000}.anim" );
			var ctrl = AssetDatabase.LoadAssetAtPath<AnimatorController>( $"{folder}/chip_{chip.id:0000}.controller" );
			if ( clip == null || ctrl == null ) { badBind++; problems.Add( $"{chip.id}: missing asset" ); continue; }
			if ( AnimationUtility.GetCurveBindings( clip ).Length == 0 ) { badBind++; problems.Add( $"{chip.id}: clip has no bindings" ); }
			var motion = ctrl.layers[0].stateMachine.defaultState?.motion;
			if ( motion != clip ) { badBind++; problems.Add( $"{chip.id}: controller default state not bound to clip" ); }
		}

		var report = new StringBuilder();
		report.AppendLine( $"chips in plan: {chips.Length}" );
		report.AppendLine( $"clips: {clips}  controllers: {controllers}  skipped: {skipped}" );
		report.AppendLine( $"aux clips: {auxClips}  aux controllers: {auxControllers}" );
		report.AppendLine( $"binding problems: {badBind}" );
		foreach ( var p in problems.Take( 40 ) ) report.AppendLine( "  " + p );
		Directory.CreateDirectory( "Logs" );
		File.WriteAllText( "Logs/chip-animation-build.txt", report.ToString() );
		Debug.Log( "[ChipAnimBuilder]\n" + report );
	}
}
