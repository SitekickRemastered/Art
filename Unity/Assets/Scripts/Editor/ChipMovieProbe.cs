#if UNITY_EDITOR
using System.IO;
using System.Text;
using UnityEditor;
using UnityEngine;

namespace Sitekick
{
	/// <summary>
	/// Prints the Sitekick prefab's landmarks in prefab-local units, which is what
	/// a stage-sized chip movie has to register against: a chip SWF is a 375x300
	/// stage whose centre sits over the Sitekick, so its art lines up with the eye
	/// only at one scale and one offset.
	/// </summary>
	public static class ChipMovieProbe
	{
		public const string PrefabPath = "Assets/Sitekick/EditorSitekick.prefab";
		public const string ReportPath = "Logs/sitekick-landmarks.txt";

		public static void Run()
		{
			var prefab = AssetDatabase.LoadAssetAtPath<GameObject>( PrefabPath );
			if ( prefab == null )
			{
				Debug.LogError( "no sitekick prefab at " + PrefabPath );
				return;
			}

			var root = prefab.transform;
			var lines = new StringBuilder();
			foreach ( var r in prefab.GetComponentsInChildren<SpriteRenderer>( true ) )
			{
				var b = r.bounds;
				lines.AppendLine( NodePath( r.transform, root ) + "  size " + b.size.ToString( "0.000" )
					+ "  centre " + b.center.ToString( "0.000" )
					+ "  localPos " + r.transform.localPosition.ToString( "0.000" )
					+ "  scale " + r.transform.lossyScale.ToString( "0.000" )
					+ "  order " + r.sortingOrder );
			}

			Directory.CreateDirectory( Path.GetDirectoryName( ReportPath ) );
			File.WriteAllText( ReportPath, lines.ToString() );
			Debug.Log( lines.ToString() );
		}

		static string NodePath( Transform t, Transform root )
		{
			var parts = new System.Collections.Generic.List<string>();
			while ( t != null && t != root )
			{
				parts.Insert( 0, t.name );
				t = t.parent;
			}
			return string.Join( "/", parts.ToArray() );
		}
	}
}
#endif
