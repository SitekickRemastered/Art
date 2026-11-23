#if UNITY_EDITOR
using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace Sitekick
{
	/// <summary>
	/// Checks a chip's colouring end to end: the effect switched on after the
	/// colour was applied has to come up in that colour, change with it, and go
	/// back to white when the colour does -- with nothing but the renderers in
	/// its ChipEffect's "Colored Renderers" list.
	///
	/// Writes Logs/chip-colour/report.txt and art.png.
	/// Batch entry point: -executeMethod Sitekick.ChipColorCheck.RunFromCommandLine
	/// </summary>
	public static class ChipColorCheck
	{
		const string ScenePath = "Assets/Scenes/ChipGallery.unity";
		const string PhaseKey = "Sitekick.ChipColorCheck.phase";
		const string LogDir = "Logs/chip-colour";

		static readonly Color Colour = new Color( 1f, 0.8f, 0f, 1f );   // FFCC00

		static int chip = 45;
		static int retries;

		[InitializeOnLoadMethod]
		static void Hook()
		{
			EditorApplication.update -= Tick;
			if ( SessionState.GetInt( PhaseKey, 0 ) > 0 )
				EditorApplication.update += Tick;
		}

		public static void RunFromCommandLine()
		{
			var args = System.Environment.GetCommandLineArgs();
			for ( var i = 0; i < args.Length - 1; i++ )
			{
				if ( args[ i ] == "--chip" )
					int.TryParse( args[ i + 1 ], out chip );
			}

			Application.runInBackground = true;
			SessionState.SetInt( PhaseKey, 1 );
			AssetDatabase.Refresh();
			EditorSceneManager.OpenScene( ScenePath, OpenSceneMode.Single );
			EditorApplication.update -= Tick;
			EditorApplication.update += Tick;
		}

		static void Tick()
		{
			if ( SessionState.GetInt( PhaseKey, 0 ) != 1 )
				return;

			if ( EditorUtility.scriptCompilationFailed )
			{
				Debug.Log( "ChipColorCheck: scripts have compile errors" );
				Finish();
			}
			else if ( EditorApplication.isPlaying )
				Run();
			else if ( !EditorApplication.isPlayingOrWillChangePlaymode )
				EditorApplication.isPlaying = true;
		}

		static void Run()
		{
			var gallery = Object.FindFirstObjectByType<ChipGallery>();
			if ( gallery == null || gallery.Sitekick == null )
			{
				if ( retries++ < 20 )
					return;
				Debug.Log( "ChipColorCheck: the gallery has no Sitekick" );
				Finish();
				return;
			}

			Directory.CreateDirectory( LogDir );
			var report = new StringBuilder();
			var ok = true;

			// spawn with the colour already set: the effect has to pick it up itself
			gallery.ApplyColor( Colour );
			gallery.Toggle( chip );

			var effect = FindEffect( gallery, chip );
			if ( effect == null )
			{
				report.AppendLine( "chip " + chip + ": never spawned" );
				Debug.Log( report );
				Finish();
				return;
			}

			var chipEffect = effect.GetComponent<ChipEffect>();
			var list = chipEffect != null ? chipEffect.ColoredRenderers : null;
			report.AppendLine( "chip " + chip + " colored renderers: " + ( list != null ? list.Count : 0 )
				+ "  at spawn colour " + Colour.ToString( "0.00" ) );

			if ( list == null || list.Count == 0 )
			{
				report.AppendLine( "  RESULT FAIL: ChipEffect has no colored renderers" );
				Debug.Log( report );
				Finish();
				return;
			}

			foreach ( var renderer in list )
			{
				var got = Tint( renderer );
				var matches = renderer != null && ( got - Colour ).maxColorComponent < 0.01f;
				report.AppendLine( "  " + ( renderer != null ? renderer.name : "missing" ) + "  tint "
					+ got.ToString( "0.0000" ) + ( matches ? "  ok" : "  MISMATCH" ) );
				ok &= matches;
			}

			SitekickColorCheck.Capture( LogDir + "/art.png", Bounds( effect ) );

			// follow a change, then go back to white
			gallery.ApplyColor( new Color( 0.2f, 0.4f, 1f, 1f ) );
			var followed = true;
			foreach ( var renderer in list )
				followed &= renderer != null && ( Tint( renderer ) - new Color( 0.2f, 0.4f, 1f, 1f ) ).maxColorComponent < 0.01f;
			report.AppendLine( "followed a colour change: " + ( followed ? "yes" : "NO" ) );
			ok &= followed;

			gallery.ApplyColor( Color.white );
			var reverted = true;
			foreach ( var renderer in list )
				reverted &= renderer != null && ( Tint( renderer ) - Color.white ).maxColorComponent < 0.01f;
			report.AppendLine( "reverted to white: " + ( reverted ? "yes" : "NO" ) );
			ok &= reverted;

			report.AppendLine( "RESULT " + ( ok ? "OK" : "FAIL" ) );
			File.WriteAllText( LogDir + "/report.txt", report.ToString() );
			Debug.Log( report.ToString() );

			Finish();
		}

		static GameObject FindEffect( ChipGallery gallery, int id )
		{
			foreach ( var effect in gallery.ActiveEffects )
			{
				if ( effect != null && effect.name == "Chip_" + id.ToString( "0000" ) + "_Effect" )
					return effect;
			}

			return null;
		}

		static Color Tint( Renderer renderer )
		{
			if ( renderer == null )
				return Color.clear;

			var block = new MaterialPropertyBlock();
			renderer.GetPropertyBlock( block );
			return block.GetColor( "_Color" );
		}

		static Bounds Bounds( GameObject effect )
		{
			var renderers = effect.GetComponentsInChildren<SpriteRenderer>( true );
			if ( renderers.Length == 0 )
				return new Bounds();

			var bounds = renderers[ 0 ].bounds;
			for ( var i = 1; i < renderers.Length; i++ )
				bounds.Encapsulate( renderers[ i ].bounds );
			return bounds;
		}

		static void Finish()
		{
			SessionState.SetInt( PhaseKey, 0 );
			EditorApplication.update -= Tick;
			EditorApplication.isPlaying = false;
			EditorApplication.delayCall += () => EditorApplication.Exit( 0 );
		}
	}
}
#endif
